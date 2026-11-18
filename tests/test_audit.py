from __future__ import annotations

import numpy as np
import pytest

from signal_audit.audit.backtest import BacktestConfig
from signal_audit.audit.baselines import buy_and_hold, permutation_test
from signal_audit.audit.report import Thresholds, Verdict, decide_verdict
from signal_audit.audit.runner import (
    CHECKS_NOT_RUN,
    ENGAGEMENT_VINTAGE_NOT_RUN,
    audit_signal,
    checks_not_run,
)
from signal_audit.data.market import MarketData
from signal_audit.signals.examples import MentionSpikeSignal, MomentumSignal, RandomSignal
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


def test_report_has_no_data_section_by_default(market: MarketData) -> None:
    report = audit_signal(RandomSignal(), market, n_permutations=20)
    assert report.universe is None and report.data_source is None and report.data_checks == []
    assert "## Data" not in report.to_markdown()


def test_report_renders_data_section_after_period(market: MarketData) -> None:
    report = audit_signal(
        RandomSignal(),
        market,
        n_permutations=20,
        universe="test_universe: AAA, BBB",
        data_source="fake 0.0, split/dividend adjusted, sha256 abc",
        data_checks=["Non-positive prices: 0", "Split suspects: 0"],
    )
    markdown = report.to_markdown()
    lines = markdown.splitlines()
    period = next(i for i, line in enumerate(lines) if line.startswith("Period "))
    assert lines[period + 2] == "## Data"
    data_block = lines[period + 4 : period + 8]
    assert data_block == [
        "- Universe: test_universe: AAA, BBB",
        "- Source: fake 0.0, split/dividend adjusted, sha256 abc",
        "- Non-positive prices: 0",
        "- Split suspects: 0",
    ]
    assert markdown.index("## Data") < markdown.index("## Leak check")
    assert report.model_validate_json(report.model_dump_json()) == report


def test_data_section_shown_for_checks_alone(market: MarketData) -> None:
    report = audit_signal(RandomSignal(), market, n_permutations=20, data_checks=["Sessions: 1"])
    assert "## Data\n\n- Sessions: 1\n" in report.to_markdown()


def test_price_only_audit_lists_only_the_standing_caveats(market: MarketData) -> None:
    prices_only = MarketData(opens=market.opens, closes=market.closes)
    report = audit_signal(MomentumSignal(), prices_only, n_permutations=20)
    assert report.checks_not_run == CHECKS_NOT_RUN
    assert "Market holidays" not in report.to_markdown()


def test_engagement_vintage_caveat_only_when_engagement_is_used(market: MarketData) -> None:
    assert market.engagement is not None
    report = audit_signal(RandomSignal(), market, n_permutations=20)
    assert ENGAGEMENT_VINTAGE_NOT_RUN in report.checks_not_run
    assert "stamped with the posting time" in report.to_markdown()

    without = MarketData(opens=market.opens, closes=market.closes, documents=market.documents)
    assert ENGAGEMENT_VINTAGE_NOT_RUN not in checks_not_run(without)


def test_caveats_when_only_engagement_is_used(market: MarketData) -> None:
    data = MarketData(opens=market.opens, closes=market.closes, engagement=market.engagement)
    assert checks_not_run(data) == [*CHECKS_NOT_RUN, ENGAGEMENT_VINTAGE_NOT_RUN]
    documents_only = MarketData(
        opens=market.opens, closes=market.closes, documents=market.documents
    )
    assert checks_not_run(documents_only) == CHECKS_NOT_RUN
