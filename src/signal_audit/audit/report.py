"""The audit report card and the rules that produce its verdict.

Verdict thresholds live here and nowhere else.
"""

from __future__ import annotations

import datetime as dt
from enum import StrEnum

from pydantic import BaseModel

from signal_audit.audit.metrics import PerformanceSummary


class Verdict(StrEnum):
    LEAK_DETECTED = "LEAK_DETECTED"
    EDGE_SURVIVES = "EDGE_SURVIVES"
    NO_EDGE = "NO_EDGE"
    INCONCLUSIVE = "INCONCLUSIVE"


class Thresholds(BaseModel):
    p_edge: float = 0.05
    p_no_edge: float = 0.20
    deflated_sharpe_edge: float = 0.95
    base_cost_bps: float = 10.0
    stress_cost_bps: float = 25.0


class LeakSummary(BaseModel):
    passed: bool
    cuts_tested: int
    mismatched_cells: int
    first_mismatch_date: dt.date | None = None
    first_mismatch_ticker: str | None = None


class AuditReport(BaseModel):
    signal: str
    start: dt.date
    end: dt.date
    n_sessions: int
    top_k: int
    n_trials: int
    leak: LeakSummary
    performance_by_cost_bps: dict[str, PerformanceSummary]
    buy_and_hold: PerformanceSummary
    permutation_p_value: float | None
    n_permutations: int
    deflated_sharpe: float | None
    thresholds: Thresholds
    verdict: Verdict
    reasons: list[str]
    checks_not_run: list[str]

    def to_markdown(self) -> str:
        lines = [
            f"# Audit report: `{self.signal}`",
            "",
            f"**Verdict: {self.verdict.value}**",
            "",
            *[f"- {reason}" for reason in self.reasons],
            "",
            f"Period {self.start} to {self.end} ({self.n_sessions} sessions), "
            f"long-only top {self.top_k}, {self.n_trials} variant(s) tried.",
            "",
            "## Leak check (truncation test)",
            "",
            f"- Result: {'passed' if self.leak.passed else 'FAILED'}",
            f"- Cut dates tested: {self.leak.cuts_tested}",
            f"- Past scores that changed: {self.leak.mismatched_cells}",
        ]
        if self.leak.first_mismatch_date is not None:
            where = f"{self.leak.first_mismatch_date} / {self.leak.first_mismatch_ticker}"
            lines.append(f"- First change: {where}")

        void = "" if self.leak.passed else " (VOID: computed from leaked scores)"
        lines += [
            "",
            f"## Performance{void}",
            "",
            "| Cost (bps) | Total return | CAGR | Sharpe | Sortino | Max drawdown |",
            "|---:|---:|---:|---:|---:|---:|",
        ]
        for cost, perf in self.performance_by_cost_bps.items():
            lines.append(_row(cost, perf))
        lines.append(_row("buy & hold", self.buy_and_hold))

        lines += ["", "## Statistics", ""]
        if self.permutation_p_value is None:
            lines.append("- Permutation test: not run (leak detected)")
        else:
            lines.append(
                f"- Permutation p-value: {self.permutation_p_value:.4f} "
                f"({self.n_permutations} shuffles, before costs)"
            )
        if self.deflated_sharpe is None:
            lines.append("- Deflated Sharpe: not run (leak detected)")
        else:
            lines.append(
                f"- Deflated Sharpe at {self.thresholds.base_cost_bps:g} bps: "
                f"{self.deflated_sharpe:.4f}"
            )

        lines += ["", "## Checks not run", "", *[f"- {item}" for item in self.checks_not_run]]
        t = self.thresholds
        lines += [
            "",
            "## Verdict rules",
            "",
            f"- EDGE_SURVIVES: no leak, p <= {t.p_edge}, deflated Sharpe >= "
            f"{t.deflated_sharpe_edge}, Sharpe at {t.stress_cost_bps:g} bps > 0",
            f"- NO_EDGE: no leak, and p > {t.p_no_edge} or Sharpe at {t.base_cost_bps:g} bps <= 0",
            "- INCONCLUSIVE: anything else",
            "",
            "_This report evaluates a signal. It is not investment advice._",
            "",
        ]
        return "\n".join(lines)


def _row(label: str, perf: PerformanceSummary) -> str:
    return (
        f"| {label} | {perf.total_return:+.1%} | {perf.cagr:+.1%} | {perf.sharpe:.2f} "
        f"| {perf.sortino:.2f} | {perf.max_drawdown:.1%} |"
    )


def decide_verdict(
    *,
    leak_passed: bool,
    permutation_p_value: float | None,
    deflated_sharpe: float | None,
    sharpe_base_cost: float,
    sharpe_stress_cost: float,
    thresholds: Thresholds,
) -> tuple[Verdict, list[str]]:
    if not leak_passed:
        return Verdict.LEAK_DETECTED, [
            "Past scores changed when future data was removed, so the signal uses "
            "information it could not have had. Its performance numbers are void."
        ]
    if permutation_p_value is None or deflated_sharpe is None:
        raise ValueError("statistics are required when no leak was detected")

    t = thresholds
    if sharpe_base_cost <= 0:
        return Verdict.NO_EDGE, [
            f"Sharpe at {t.base_cost_bps:g} bps is {sharpe_base_cost:.2f}, which is not positive."
        ]
    if permutation_p_value > t.p_no_edge:
        return Verdict.NO_EDGE, [
            f"Shuffled scores did as well or better {permutation_p_value:.0%} of the time "
            f"(threshold {t.p_no_edge:.0%})."
        ]
    if (
        permutation_p_value <= t.p_edge
        and deflated_sharpe >= t.deflated_sharpe_edge
        and sharpe_stress_cost > 0
    ):
        return Verdict.EDGE_SURVIVES, [
            "No look-ahead found.",
            f"Beats shuffled scores (p = {permutation_p_value:.4f}).",
            f"Deflated Sharpe {deflated_sharpe:.3f} clears {t.deflated_sharpe_edge}.",
            f"Still positive at {t.stress_cost_bps:g} bps (Sharpe {sharpe_stress_cost:.2f}).",
        ]

    reasons = ["No look-ahead found, but the evidence is not strong enough either way."]
    if permutation_p_value > t.p_edge:
        reasons.append(f"Permutation p = {permutation_p_value:.4f} is above {t.p_edge}.")
    if deflated_sharpe < t.deflated_sharpe_edge:
        reasons.append(f"Deflated Sharpe {deflated_sharpe:.3f} is below {t.deflated_sharpe_edge}.")
    if sharpe_stress_cost <= 0:
        reasons.append(
            f"Sharpe at {t.stress_cost_bps:g} bps is {sharpe_stress_cost:.2f}; "
            "the result does not survive higher costs."
        )
    return Verdict.INCONCLUSIVE, reasons
