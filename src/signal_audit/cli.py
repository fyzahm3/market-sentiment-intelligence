"""Command-line entry point: ``sigaudit``."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from signal_audit import __version__
from signal_audit.audit.report import AuditReport, Verdict
from signal_audit.audit.runner import audit_signal, run_leak_suite
from signal_audit.config import get_settings
from signal_audit.data.synthetic import synthetic_market
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
    for column in (
        "Signal",
        "Verdict",
        "Leak check",
        "Sharpe @10bps",
        "Sharpe @25bps",
        "Perm. p",
        "Deflated Sharpe",
    ):
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
