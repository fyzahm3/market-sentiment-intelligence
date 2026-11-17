"""Runs every check on a signal and assembles the report card."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from signal_audit.audit.backtest import BacktestConfig, run_backtest
from signal_audit.audit.baselines import buy_and_hold, permutation_test
from signal_audit.audit.leakage import truncation_test
from signal_audit.audit.metrics import PerformanceSummary, deflated_sharpe_ratio, summarize
from signal_audit.audit.report import AuditReport, LeakSummary, Thresholds, decide_verdict
from signal_audit.data.market import MarketData
from signal_audit.signals.base import Signal, align_scores
from signal_audit.signals.examples import honest_signals
from signal_audit.signals.planted import planted_leaks

CHECKS_NOT_RUN = [
    "Model memory: whether an LLM behind the signal saw this period in training.",
    "Survivorship: whether the ticker universe was chosen with hindsight.",
]
HOLIDAYS_NOT_RUN = "Market holidays: every weekday is treated as a trading session."


def checks_not_run(data: MarketData) -> list[str]:
    """Checks the report card cannot vouch for, given the data the audit ran on.

    Price-only data takes its sessions from the real price index, so the
    weekday-session assumption only matters when documents are mapped to
    session closes.
    """
    items = list(CHECKS_NOT_RUN)
    if data.documents is not None:
        items.append(HOLIDAYS_NOT_RUN)
    return items


def audit_signal(
    signal: Signal,
    data: MarketData,
    *,
    top_k: int = 3,
    n_trials: int = 1,
    n_permutations: int = 500,
    seed: int = 0,
    thresholds: Thresholds | None = None,
    universe: str | None = None,
    data_source: str | None = None,
    data_checks: list[str] | None = None,
) -> AuditReport:
    """Audit ``signal`` on ``data``.

    ``n_trials`` is the number of variants of this signal that were tried
    before settling on this one. Reporting it honestly is what makes the
    deflated Sharpe ratio meaningful.

    ``universe``, ``data_source`` and ``data_checks`` describe the data and are
    copied onto the report card unchanged.
    """
    thresholds = thresholds or Thresholds()
    leak = truncation_test(signal, data)
    scores = align_scores(signal.compute(data), data)

    cost_levels = sorted({0.0, thresholds.base_cost_bps, thresholds.stress_cost_bps})
    results = {
        cost: run_backtest(scores, data, BacktestConfig(top_k=top_k, cost_bps=cost))
        for cost in cost_levels
    }
    performance: dict[str, PerformanceSummary] = {
        f"{cost:g}": summarize(result.returns, result.turnover) for cost, result in results.items()
    }
    base = results[thresholds.base_cost_bps]

    permutation_p: float | None = None
    deflated: float | None = None
    if leak.passed:
        permutation_p = permutation_test(
            scores,
            data,
            BacktestConfig(top_k=top_k),
            rng=np.random.default_rng(seed),
            n_permutations=n_permutations,
        ).p_value
        deflated = deflated_sharpe_ratio(base.returns, n_trials=n_trials)

    verdict, reasons = decide_verdict(
        leak_passed=leak.passed,
        permutation_p_value=permutation_p,
        deflated_sharpe=deflated,
        sharpe_base_cost=performance[f"{thresholds.base_cost_bps:g}"].sharpe,
        sharpe_stress_cost=performance[f"{thresholds.stress_cost_bps:g}"].sharpe,
        thresholds=thresholds,
    )

    first = leak.first_mismatch
    return AuditReport(
        signal=signal.name,
        start=data.dates[0].date(),
        end=data.dates[-1].date(),
        n_sessions=len(data.dates),
        top_k=top_k,
        n_trials=n_trials,
        leak=LeakSummary(
            passed=leak.passed,
            cuts_tested=len(leak.cuts),
            mismatched_cells=leak.mismatched_cells,
            first_mismatch_date=None if first is None else first[0].date(),
            first_mismatch_ticker=None if first is None else first[1],
        ),
        performance_by_cost_bps=performance,
        buy_and_hold=summarize(buy_and_hold(data)),
        permutation_p_value=permutation_p,
        n_permutations=n_permutations if leak.passed else 0,
        deflated_sharpe=deflated,
        thresholds=thresholds,
        verdict=verdict,
        reasons=reasons,
        checks_not_run=checks_not_run(data),
        universe=universe,
        data_source=data_source,
        data_checks=list(data_checks or []),
    )


@dataclass(frozen=True)
class LeakSuiteRow:
    signal: str
    has_leak: bool
    flagged: bool
    mismatched_cells: int

    @property
    def correct(self) -> bool:
        return self.has_leak == self.flagged


def run_leak_suite(data: MarketData) -> list[LeakSuiteRow]:
    """Run the truncation test on signals whose leak status is known."""
    rows = []
    for has_leak, signals in ((False, honest_signals()), (True, planted_leaks())):
        for signal in signals:
            report = truncation_test(signal, data)
            rows.append(
                LeakSuiteRow(
                    signal=signal.name,
                    has_leak=has_leak,
                    flagged=not report.passed,
                    mismatched_cells=report.mismatched_cells,
                )
            )
    return rows
