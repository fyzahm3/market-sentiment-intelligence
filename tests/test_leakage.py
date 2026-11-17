from __future__ import annotations

import pandas as pd
import pytest

from signal_audit.audit.leakage import choose_cuts, truncation_test
from signal_audit.audit.runner import run_leak_suite
from signal_audit.data.market import MarketData
from signal_audit.signals.base import Signal
from signal_audit.signals.examples import EngagementSignal, honest_signals
from signal_audit.signals.planted import (
    ArchivedEngagementSignal,
    PeekAheadSignal,
    planted_leaks,
)


@pytest.mark.parametrize("signal", honest_signals(), ids=lambda s: s.name)
def test_truncation_passes_honest_signals(signal: Signal, market: MarketData) -> None:
    report = truncation_test(signal, market)
    assert report.passed
    assert report.mismatched_cells == 0
    assert report.first_mismatch is None


@pytest.mark.parametrize("signal", planted_leaks(), ids=lambda s: s.name)
def test_truncation_flags_planted_leaks(signal: Signal, market: MarketData) -> None:
    report = truncation_test(signal, market)
    assert not report.passed
    assert report.mismatched_cells > 0
    assert report.first_mismatch is not None


def test_first_mismatch_is_before_the_cut(market: MarketData) -> None:
    report = truncation_test(PeekAheadSignal(), market)
    failing = [cut for cut in report.cuts if not cut.passed]
    assert failing
    for cut in failing:
        assert cut.first_mismatch is not None
        assert cut.first_mismatch[0] <= cut.cut


def test_leak_suite_is_fully_correct(market: MarketData) -> None:
    rows = run_leak_suite(market)
    assert len(rows) == len(honest_signals()) + len(planted_leaks())
    assert all(row.correct for row in rows)


def test_leak_suite_covers_engagement(market: MarketData) -> None:
    rows = {row.signal: row for row in run_leak_suite(market)}
    honest = rows[EngagementSignal().name]
    leaky = rows[ArchivedEngagementSignal().name]
    assert not honest.has_leak and not honest.flagged and honest.mismatched_cells == 0
    assert leaky.has_leak and leaky.flagged and leaky.mismatched_cells > 0


def test_archived_engagement_changes_scores_just_before_the_cut(market: MarketData) -> None:
    report = truncation_test(ArchivedEngagementSignal(), market)
    for cut in report.cuts:
        assert not cut.passed
        assert cut.first_mismatch is not None
        # Final snapshots are a week old, so only the last few sessions can change.
        assert cut.cut - cut.first_mismatch[0] <= pd.Timedelta(days=7)


def test_choose_cuts_leaves_future_to_remove(market: MarketData) -> None:
    cuts = choose_cuts(market.dates, n_cuts=5, min_history=90)
    assert len(cuts) == 5
    assert cuts[0] == market.dates[90]
    assert cuts[-1] < market.dates[-1]


def test_choose_cuts_needs_enough_history(market: MarketData) -> None:
    short = market.truncate(market.dates[50])
    with pytest.raises(ValueError, match="need more than"):
        choose_cuts(short.dates, n_cuts=5, min_history=90)
