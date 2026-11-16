from __future__ import annotations

import numpy as np
import pytest

from signal_audit.audit.backtest import BacktestConfig
from signal_audit.audit.baselines import buy_and_hold, permutation_test
from signal_audit.audit.report import Thresholds, Verdict, decide_verdict
from signal_audit.audit.runner import audit_signal
from signal_audit.data.market import MarketData
from signal_audit.signals.examples import MentionSpikeSignal, RandomSignal
from signal_audit.signals.planted import PeekAheadSignal


def test_permutation_test_finds_the_planted_effect(market: MarketData) -> None:
    scores = MentionSpikeSignal().compute(market)
    result = permutation_test(
        scores, market, BacktestConfig(), rng=np.random.default_rng(0), n_permutations=200
    )
    assert result.n_permutations == 200
    assert result.p_value < 0.05


def test_permutation_test_does_not_reward_noise(flat_market: MarketData) -> None:
    scores = RandomSignal(seed=3).compute(flat_market)
    result = permutation_test(
        scores, flat_market, BacktestConfig(), rng=np.random.default_rng(0), n_permutations=200
    )
    assert result.p_value > 0.05


def test_permutation_p_value_is_never_zero(market: MarketData) -> None:
    scores = PeekAheadSignal().compute(market)
    result = permutation_test(
        scores, market, BacktestConfig(), rng=np.random.default_rng(0), n_permutations=20
    )
    assert result.p_value == pytest.approx(1 / 21)


def test_buy_and_hold_drops_last_session(market: MarketData) -> None:
    assert len(buy_and_hold(market)) == len(market.dates) - 1


def test_audit_flags_leak_and_skips_statistics(market: MarketData) -> None:
    report = audit_signal(PeekAheadSignal(), market, n_permutations=20)
    assert report.verdict is Verdict.LEAK_DETECTED
    assert report.permutation_p_value is None
    assert report.deflated_sharpe is None
    assert report.leak.first_mismatch_date is not None
    assert "VOID" in report.to_markdown()


def test_audit_planted_edge_survives(market: MarketData) -> None:
    report = audit_signal(MentionSpikeSignal(), market, n_permutations=200)
    assert report.leak.passed
    assert report.verdict is Verdict.EDGE_SURVIVES
    assert set(report.performance_by_cost_bps) == {"0", "10", "25"}


def test_audit_noise_has_no_edge(flat_market: MarketData) -> None:
    report = audit_signal(RandomSignal(), flat_market, n_permutations=100)
    assert report.leak.passed
    assert report.verdict is Verdict.NO_EDGE


def test_more_trials_lower_the_deflated_sharpe(market: MarketData) -> None:
    one = audit_signal(MentionSpikeSignal(), market, n_permutations=20, n_trials=1)
    many = audit_signal(MentionSpikeSignal(), market, n_permutations=20, n_trials=500)
    assert one.deflated_sharpe is not None and many.deflated_sharpe is not None
    assert many.deflated_sharpe < one.deflated_sharpe


def test_report_serialises(market: MarketData) -> None:
    report = audit_signal(RandomSignal(), market, n_permutations=20)
    assert report.model_validate_json(report.model_dump_json()) == report
    assert report.to_markdown().startswith("# Audit report: `random`")


@pytest.mark.parametrize(
    ("p", "dsr", "base", "stress", "expected"),
    [
        (0.01, 0.99, 1.5, 0.8, Verdict.EDGE_SURVIVES),
        (0.01, 0.99, 1.5, -0.1, Verdict.INCONCLUSIVE),
        (0.01, 0.80, 1.5, 0.8, Verdict.INCONCLUSIVE),
        (0.10, 0.99, 1.5, 0.8, Verdict.INCONCLUSIVE),
        (0.50, 0.99, 1.5, 0.8, Verdict.NO_EDGE),
        (0.01, 0.99, -0.2, -0.9, Verdict.NO_EDGE),
    ],
)
def test_verdict_rules(p: float, dsr: float, base: float, stress: float, expected: Verdict) -> None:
    verdict, reasons = decide_verdict(
        leak_passed=True,
        permutation_p_value=p,
        deflated_sharpe=dsr,
        sharpe_base_cost=base,
        sharpe_stress_cost=stress,
        thresholds=Thresholds(),
    )
    assert verdict is expected
    assert reasons


def test_leak_overrides_everything() -> None:
    verdict, _ = decide_verdict(
        leak_passed=False,
        permutation_p_value=None,
        deflated_sharpe=None,
        sharpe_base_cost=30.0,
        sharpe_stress_cost=25.0,
        thresholds=Thresholds(),
    )
    assert verdict is Verdict.LEAK_DETECTED
