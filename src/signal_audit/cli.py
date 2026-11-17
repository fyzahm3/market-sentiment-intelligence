"""Command-line entry point: ``sigaudit``."""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from signal_audit import __version__
from signal_audit.audit.report import AuditReport, Verdict
from signal_audit.audit.runner import audit_signal, run_leak_suite
from signal_audit.config import get_settings
from signal_audit.data.adapters.prices import PriceCacheError, load_prices_cached
from signal_audit.data.sanity import FAILING_KINDS, check_prices
from signal_audit.data.synthetic import synthetic_market
from signal_audit.data.universe import load_universe
from signal_audit.ledger import Ledger, LedgerError
from signal_audit.signals.base import Signal
from signal_audit.signals.examples import MentionSpikeSignal, MomentumSignal, RandomSignal
from signal_audit.signals.planted import PeekAheadSignal

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Test whether a trading signal has a real edge. Not investment advice.",
)
ledger_app = typer.Typer(no_args_is_help=True, help="Inspect the forward ledger.")
app.add_typer(ledger_app, name="ledger")

console = Console()

_VERDICT_STYLE = {
    Verdict.LEAK_DETECTED: "bold red",
    Verdict.EDGE_SURVIVES: "bold green",
    Verdict.NO_EDGE: "yellow",
    Verdict.INCONCLUSIVE: "cyan",
}


@app.command()
def version() -> None:
    """Print the installed version."""
    console.print(__version__)


@app.command()
def demo(
    seed: Annotated[int, typer.Option(help="Seed for the synthetic market.")] = 7,
    permutations: Annotated[int, typer.Option(help="Shuffles for the permutation test.")] = 500,
    out: Annotated[
        Path | None, typer.Option(help="Directory to write full report cards to.")
    ] = None,
) -> None:
    """Audit four reference signals on synthetic data with a planted effect."""
    console.print(
        "[dim]Synthetic data with a known planted effect. "
        "These results say nothing about real markets.[/dim]\n"
    )
    data = synthetic_market(seed=seed)
    signals: list[Signal] = [
        MentionSpikeSignal(),
        MomentumSignal(),
        RandomSignal(),
        PeekAheadSignal(),
    ]
    reports = [audit_signal(s, data, n_permutations=permutations) for s in signals]

    table = Table(title="Audit results")
    for column in _SUMMARY_COLUMNS:
        table.add_column(column)
    for report in reports:
        table.add_row(*_summary_row(report))
    console.print(table)

    for report in reports:
        console.print(f"\n[bold]{report.signal}[/bold]")
        for reason in report.reasons:
            console.print(f"  {reason}")

    if out is not None:
        out.mkdir(parents=True, exist_ok=True)
        for report in reports:
            (out / f"{report.signal}.md").write_text(report.to_markdown(), encoding="utf-8")
            (out / f"{report.signal}.json").write_text(
                report.model_dump_json(indent=2), encoding="utf-8"
            )
        console.print(f"\nReport cards written to {out}/")


_SUMMARY_COLUMNS = (
    "Signal",
    "Verdict",
    "Leak check",
    "Sharpe @10bps",
    "Sharpe @25bps",
    "Perm. p",
    "Deflated Sharpe",
)


def _summary_row(report: AuditReport) -> list[str]:
    style = _VERDICT_STYLE[report.verdict]
    perf = report.performance_by_cost_bps
    void = "" if report.leak.passed else " (void)"
    return [
        report.signal,
        f"[{style}]{report.verdict.value}[/{style}]",
        "passed" if report.leak.passed else "FAILED",
        f"{perf['10'].sharpe:.2f}{void}",
        f"{perf['25'].sharpe:.2f}{void}",
        "-" if report.permutation_p_value is None else f"{report.permutation_p_value:.4f}",
        "-" if report.deflated_sharpe is None else f"{report.deflated_sharpe:.3f}",
    ]


# Signals that need nothing but prices. Document-based signals need a document
# source that does not exist for real data yet (milestone M2).
PRICE_SIGNALS: dict[str, Callable[[], Signal]] = {
    "momentum": MomentumSignal,
    "random": RandomSignal,
}

_MAX_ISSUES_SHOWN = 20


def _iso_date(value: str, option: str) -> str:
    try:
        return dt.date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise typer.BadParameter(f"expected YYYY-MM-DD, got {value!r}", param_hint=option) from exc


@app.command()
def audit(
    signal: Annotated[str, typer.Option(help=f"Signal to audit: {', '.join(PRICE_SIGNALS)}.")],
    universe: Annotated[
        Path,
        typer.Option(
            exists=True, dir_okay=False, help="Ticker file: one per line, # comments allowed."
        ),
    ],
    start: Annotated[str, typer.Option(help="First date, YYYY-MM-DD.")],
    end: Annotated[str, typer.Option(help="End date, YYYY-MM-DD (exclusive, as in yfinance).")],
    top_k: Annotated[int, typer.Option(min=1, help="Tickers held each day.")] = 3,
    permutations: Annotated[
        int, typer.Option(min=1, help="Shuffles for the permutation test.")
    ] = 500,
    seed: Annotated[int, typer.Option(help="Seed for the permutation test.")] = 0,
    n_trials: Annotated[
        int, typer.Option(min=1, help="Variants of this signal tried, for the deflated Sharpe.")
    ] = 1,
    out: Annotated[Path | None, typer.Option(help="Directory to write the report card to.")] = None,
    refresh: Annotated[
        bool, typer.Option(help="Download prices again instead of using the cache.")
    ] = False,
) -> None:
    """Audit a price-only signal on real daily prices for a ticker universe."""
    if signal not in PRICE_SIGNALS:
        raise typer.BadParameter(
            f"allowed: {', '.join(PRICE_SIGNALS)} (signals that need prices only); got {signal!r}.",
            param_hint="--signal",
        )
    start = _iso_date(start, "--start")
    end = _iso_date(end, "--end")
    if start >= end:
        raise typer.BadParameter("--start must be before --end", param_hint="--start")
    try:
        tickers = load_universe(universe)
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint="--universe") from exc

    cache_dir = get_settings().data_dir
    try:
        data, source = load_prices_cached(tickers, start, end, cache_dir, refresh=refresh)
    except (RuntimeError, ValueError) as exc:
        # PriceCacheError is a RuntimeError; download failures surface here too.
        kind = "Price cache error" if isinstance(exc, PriceCacheError) else "Price load failed"
        console.print(f"[bold red]{kind}:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc

    console.print(f"Prices: {source.describe()}")
    console.print(f"Cache: {source.cache_file}")
    sanity = check_prices(data)
    checks = sanity.to_lines()
    console.print("Data checks:")
    for line in checks:
        console.print(f"  {line}")
    if not sanity.passed:
        failing = [i for i in sanity.issues if i.kind in FAILING_KINDS]
        console.print(
            f"[bold red]Price sanity checks failed ({len(failing)} issue(s)); "
            "not auditing.[/bold red]"
        )
        for issue in failing[:_MAX_ISSUES_SHOWN]:
            console.print(f"  {issue.kind} {issue.date:%Y-%m-%d} {issue.ticker}: {issue.detail}")
        if len(failing) > _MAX_ISSUES_SHOWN:
            console.print(f"  ... and {len(failing) - _MAX_ISSUES_SHOWN} more")
        raise typer.Exit(code=1)

    report = audit_signal(
        PRICE_SIGNALS[signal](),
        data,
        top_k=top_k,
        n_trials=n_trials,
        n_permutations=permutations,
        seed=seed,
        universe=f"{universe.stem}: {', '.join(tickers)}",
        data_source=source.describe(),
        data_checks=checks,
    )

    table = Table(title="Audit result")
    for column in _SUMMARY_COLUMNS:
        table.add_column(column)
    table.add_row(*_summary_row(report))
    console.print(table)
    for reason in report.reasons:
        console.print(f"  {reason}")

    if out is not None:
        out.mkdir(parents=True, exist_ok=True)
        stem = f"{signal}_{universe.stem}"
        md_path = out / f"{stem}.md"
        json_path = out / f"{stem}.json"
        md_path.write_text(report.to_markdown(), encoding="utf-8")
        json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        console.print(f"\nReport card written to {md_path} and {json_path}")


@app.command("leak-suite")
def leak_suite(
    seed: Annotated[int, typer.Option(help="Seed for the synthetic market.")] = 7,
) -> None:
    """Run the leak check on signals whose leak status is known in advance."""
    rows = run_leak_suite(synthetic_market(seed=seed))

    table = Table(title="Planted-leak suite")
    for column in ("Signal", "Has a leak", "Flagged", "Past scores changed", "Correct"):
        table.add_column(column)
    for row in rows:
        table.add_row(
            row.signal,
            "yes" if row.has_leak else "no",
            "yes" if row.flagged else "no",
            str(row.mismatched_cells),
            "[green]yes[/green]" if row.correct else "[bold red]NO[/bold red]",
        )
    console.print(table)

    leaks = [r for r in rows if r.has_leak]
    honest = [r for r in rows if not r.has_leak]
    caught = sum(r.flagged for r in leaks)
    false_alarms = sum(r.flagged for r in honest)
    console.print(
        f"Planted leaks caught: {caught}/{len(leaks)}. "
        f"Honest signals wrongly flagged: {false_alarms}/{len(honest)}."
    )
    if caught != len(leaks) or false_alarms:
        raise typer.Exit(code=1)


@ledger_app.command("verify")
def ledger_verify(
    path: Annotated[
        Path | None, typer.Argument(help="Ledger file. Defaults to the configured path.")
    ] = None,
) -> None:
    """Check that no ledger entry has been altered, removed or back-dated."""
    target = path or get_settings().ledger_path
    if not target.exists():
        console.print(f"No ledger at {target}.")
        raise typer.Exit(code=1)
    try:
        count = Ledger(target).verify()
    except LedgerError as error:
        console.print(f"[bold red]Ledger verification failed:[/bold red] {error}")
        raise typer.Exit(code=1) from error
    console.print(f"[green]Ledger intact:[/green] {count} entries verified.")


if __name__ == "__main__":
    app()
