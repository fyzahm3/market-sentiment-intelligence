"""Command-line entry point: ``sigaudit``."""

from __future__ import annotations

import datetime as dt
import math
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
from signal_audit.data.adapters.prices import PriceCacheError, PriceSource, load_prices_cached
from signal_audit.data.collector import collect_from_settings
from signal_audit.data.market import MarketData
from signal_audit.data.sanity import FAILING_KINDS, check_prices
from signal_audit.data.synthetic import synthetic_market
from signal_audit.data.universe import load_universe
from signal_audit.ledger import Ledger, LedgerError, OutcomeLog
from signal_audit.ledger.ledger import prediction_deadline
from signal_audit.ledger.outcomes import (
    OUTCOME_COST_BPS,
    due_entries,
    holding_window,
    score_entries,
)
from signal_audit.sessions import NEW_YORK, is_session, last_completed_session
from signal_audit.signals.base import Signal, align_scores
from signal_audit.signals.examples import MentionSpikeSignal, MomentumSignal, RandomSignal
from signal_audit.signals.planted import PeekAheadSignal

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Test whether a trading signal has a real edge. Not investment advice.",
)
ledger_app = typer.Typer(no_args_is_help=True, help="Record, score and verify the forward ledger.")
app.add_typer(ledger_app, name="ledger")
collect_app = typer.Typer(no_args_is_help=True, help="Collect point-in-time social data.")
app.add_typer(collect_app, name="collect")

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


def _load_checked_prices(
    tickers: list[str], start: str, end: str, *, refresh: bool, action: str
) -> tuple[MarketData, PriceSource, list[str]]:
    """Load prices and run the sanity checks, exiting with code 1 on any failure."""
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
            f"not {action}.[/bold red]"
        )
        for issue in failing[:_MAX_ISSUES_SHOWN]:
            console.print(f"  {issue.kind} {issue.date:%Y-%m-%d} {issue.ticker}: {issue.detail}")
        if len(failing) > _MAX_ISSUES_SHOWN:
            console.print(f"  ... and {len(failing) - _MAX_ISSUES_SHOWN} more")
        raise typer.Exit(code=1)
    return data, source, checks


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

    data, source, checks = _load_checked_prices(
        tickers, start, end, refresh=refresh, action="auditing"
    )

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


# Calendar days of prices downloaded before ``as_of`` when recording. Enough for
# the longest lookback among PRICE_SIGNALS (momentum: 20 sessions) with room
# for holidays.
RECORD_HISTORY_DAYS = 90
# Calendar days of prices downloaded before the earliest entry being scored, so
# the session before it (which sets turnover) is always included.
SCORE_HISTORY_DAYS = 10


def _now() -> dt.datetime:
    """The current time in UTC. Tests replace this."""
    return dt.datetime.now(dt.UTC)


def _verified_ledger(path: Path) -> Ledger:
    ledger = Ledger(path)
    try:
        ledger.verify()
    except LedgerError as error:
        console.print(f"[bold red]Ledger verification failed:[/bold red] {error}")
        raise typer.Exit(code=1) from error
    return ledger


@ledger_app.command("record")
def ledger_record(
    signal: Annotated[str, typer.Option(help=f"Signal to record: {', '.join(PRICE_SIGNALS)}.")],
    universe: Annotated[
        Path,
        typer.Option(
            exists=True, dir_okay=False, help="Ticker file: one per line, # comments allowed."
        ),
    ],
    top_k: Annotated[int, typer.Option(min=1, help="Tickers the prediction holds.")] = 3,
    ledger: Annotated[
        Path | None, typer.Option(help="Ledger file. Defaults to the configured path.")
    ] = None,
) -> None:
    """Record the latest scores of a price-only signal, before the next session opens.

    Uses the latest completed NYSE session as ``as_of``. Exits 0 without
    writing if that session is already recorded or its price bar is not
    available yet.
    """
    if signal not in PRICE_SIGNALS:
        raise typer.BadParameter(
            f"allowed: {', '.join(PRICE_SIGNALS)} (signals that need prices only); got {signal!r}.",
            param_hint="--signal",
        )
    try:
        tickers = load_universe(universe)
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint="--universe") from exc
    name = universe.stem
    path = ledger or get_settings().ledger_path

    now = _now()
    today = now.astimezone(NEW_YORK).date()
    as_of = last_completed_session(now)
    if not is_session(today):
        console.print(f"{today} is not an NYSE session. Last completed session: {as_of}.")

    book = _verified_ledger(path)
    existing = book.find(signal, name, as_of)
    if existing is not None:
        console.print(
            f"Already recorded: {signal} on {name} as of {as_of} (entry {existing.seq}). "
            "Nothing appended."
        )
        return
    deadline = prediction_deadline(as_of)
    if now >= deadline:
        console.print(
            f"[bold red]Too late to record {as_of}:[/bold red] predictions closed at "
            f"{deadline:%Y-%m-%d %H:%M} UTC. Run again after today's close."
        )
        raise typer.Exit(code=1)

    start = (as_of - dt.timedelta(days=RECORD_HISTORY_DAYS)).isoformat()
    end = (as_of + dt.timedelta(days=1)).isoformat()  # exclusive
    data, source, _ = _load_checked_prices(tickers, start, end, refresh=True, action="recording")

    latest = data.dates[-1].date()
    if latest != as_of:
        console.print(
            f"Latest price bar is {latest}, not the last completed session {as_of}. "
            "The data is not available yet; nothing recorded."
        )
        return

    # The signal sees only data up to as_of; this row is its prediction.
    row = align_scores(PRICE_SIGNALS[signal]().compute(data), data).iloc[-1]
    values = {str(t): float(v) for t, v in zip(row.index, row.to_numpy(), strict=True)}
    scores = {t: v for t, v in values.items() if math.isfinite(v)}
    no_opinion = [t for t in values if t not in scores]
    if not scores:
        console.print(f"[bold red]{signal} has no score for any ticker on {as_of}.[/bold red]")
        raise typer.Exit(code=1)
    if no_opinion:
        console.print(f"No score (no opinion) for: {', '.join(no_opinion)}")

    try:
        entry = book.append(signal, as_of, scores, made_at=_now(), universe=name, top_k=top_k)
    except LedgerError as error:
        console.print(f"[bold red]Not recorded:[/bold red] {error}")
        raise typer.Exit(code=1) from error
    console.print(
        f"[green]Recorded[/green] {signal} on {name} as of {as_of}, top {top_k}: "
        f"entry {entry.seq}, hash {entry.hash[:12]}. Prices sha256 {source.sha256[:12]}."
    )


@ledger_app.command("score")
def ledger_score(
    ledger: Annotated[
        Path | None, typer.Option(help="Ledger file. Defaults to the configured path.")
    ] = None,
    outcomes: Annotated[
        Path | None, typer.Option(help="Outcomes file. Defaults to the configured path.")
    ] = None,
) -> None:
    """Append the realised return of every entry whose holding period has ended.

    Each entry is bought at the open of the session after ``as_of`` and sold at
    the following session's open. Predictions are never edited; outcomes go to
    their own hash-chained file.
    """
    settings = get_settings()
    ledger_path = ledger or settings.ledger_path
    outcomes_path = outcomes or settings.outcomes_path
    if not ledger_path.exists():
        console.print(f"No ledger at {ledger_path}; nothing to score.")
        return
    entries = _verified_ledger(ledger_path).entries()
    log = OutcomeLog(outcomes_path)
    try:
        log.verify(entries)
    except LedgerError as error:
        console.print(f"[bold red]Outcome verification failed:[/bold red] {error}")
        raise typer.Exit(code=1) from error

    scored_seqs = log.scored_seqs()
    now = _now()
    due = due_entries(entries, scored_seqs, now)
    waiting = len(entries) - len(scored_seqs) - len(due)
    if not due:
        console.print(
            f"Nothing to score: {len(scored_seqs)} scored, {waiting} still in their holding period."
        )
        return

    by_seq = {e.seq: e for e in entries}
    due_signals = {(by_seq[s].signal, by_seq[s].universe) for s in due}
    tickers = sorted(
        {t for e in entries if (e.signal, e.universe) in due_signals for t in e.scores}
    )
    first = min(by_seq[s].as_of for s in due)
    last_exit = max(holding_window(by_seq[s].as_of)[1] for s in due)
    start = (first - dt.timedelta(days=SCORE_HISTORY_DAYS)).isoformat()
    end = (last_exit + dt.timedelta(days=1)).isoformat()  # exclusive
    data, source, _ = _load_checked_prices(tickers, start, end, refresh=True, action="scoring")

    try:
        run = score_entries(entries, due, data, now)
        written = [log.append(s, source.describe(), entries, made_at=_now()) for s in run.scored]
    except LedgerError as error:
        console.print(f"[bold red]Scoring failed:[/bold red] {error}")
        raise typer.Exit(code=1) from error

    if written:
        table = Table(title="Outcomes appended")
        for column in (
            "Entry",
            "Signal",
            "As of",
            "Held",
            "Gross",
            f"Net @{OUTCOME_COST_BPS:g}bps",
        ):
            table.add_column(column)
        for outcome in written:
            table.add_row(
                str(outcome.entry_seq),
                f"{outcome.signal} ({outcome.universe})",
                str(outcome.as_of),
                f"{outcome.entered} to {outcome.exited} open",
                f"{outcome.gross_return:+.4%}",
                f"{outcome.net_return:+.4%}",
            )
        console.print(table)
    console.print(f"Scored {len(written)} entries; {len(run.pending) + waiting} pending.")
    for skipped in run.pending:
        console.print(f"  pending: entry {skipped.entry.seq}: {skipped.reason}")
    if run.failed:
        console.print(f"[bold red]{len(run.failed)} entries could not be scored:[/bold red]")
        for skipped in run.failed:
            console.print(f"  entry {skipped.entry.seq} ({skipped.entry.as_of}): {skipped.reason}")
        raise typer.Exit(code=1)


@ledger_app.command("verify")
def ledger_verify(
    path: Annotated[
        Path | None, typer.Argument(help="Ledger file. Defaults to the configured path.")
    ] = None,
    outcomes: Annotated[
        Path | None,
        typer.Option(
            help="Outcomes file to check against the ledger. Defaults to the configured "
            "path when the ledger is the configured one."
        ),
    ] = None,
) -> None:
    """Check that no ledger entry or outcome has been altered, removed or back-dated."""
    settings = get_settings()
    target = path or settings.ledger_path
    if not target.exists():
        console.print(f"No ledger at {target}.")
        raise typer.Exit(code=1)
    try:
        count = Ledger(target).verify()
    except LedgerError as error:
        console.print(f"[bold red]Ledger verification failed:[/bold red] {error}")
        raise typer.Exit(code=1) from error
    console.print(f"[green]Ledger intact:[/green] {count} entries verified.")

    outcomes_path = outcomes or (settings.outcomes_path if path is None else None)
    if outcomes_path is None:
        console.print("Outcomes not checked (pass --outcomes to check them).")
        return
    if not outcomes_path.exists():
        if outcomes is not None:
            console.print(f"No outcomes file at {outcomes_path}.")
            raise typer.Exit(code=1)
        console.print(f"No outcomes at {outcomes_path} yet.")
        return
    try:
        scored = OutcomeLog(outcomes_path).verify(Ledger(target).entries())
    except LedgerError as error:
        console.print(f"[bold red]Outcome verification failed:[/bold red] {error}")
        raise typer.Exit(code=1) from error
    console.print(f"[green]Outcomes intact:[/green] {scored} outcomes verified.")


@collect_app.command("reddit")
def collect_reddit(
    universe: Annotated[
        Path,
        typer.Option(
            exists=True, dir_okay=False, help="Tickers to tag: one per line, # comments allowed."
        ),
    ],
) -> None:
    """Discover new posts and re-snapshot tracked ones through the official Reddit API.

    Stores post ids, timestamps, engagement counts and tickers only, never text.
    Without credentials it skips and says so.
    """
    try:
        tickers = load_universe(universe)
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint="--universe") from exc
    summary = collect_from_settings(get_settings(), tickers)
    if summary.skipped:
        console.print(f"[yellow]{summary.describe()}[/yellow]")
        return
    console.print(summary.describe())


if __name__ == "__main__":
    app()
