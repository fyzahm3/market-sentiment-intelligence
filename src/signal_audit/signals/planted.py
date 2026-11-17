"""Deliberately leaky signals.

Each one contains a specific, common look-ahead bug. They exist so the leak
check can be measured against known answers. When a new kind of leak is found
in the wild, add it here with a test before fixing the detector.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from signal_audit.data.market import MarketData
from signal_audit.signals.base import Signal, document_counts, engagement_scores


@dataclass(frozen=True)
class PeekAheadSignal:
    """Scores each ticker with the very return the backtest is about to pay it.

    The open-to-open return from T+1 to T+2 is not known until two sessions
    after the score is supposedly made.
    """

    name: str = "leak_future_return"

    def compute(self, data: MarketData) -> pd.DataFrame:
        return data.opens.shift(-2) / data.opens.shift(-1) - 1.0


@dataclass(frozen=True)
class FullSampleZScoreSignal:
    """Normalises momentum with a mean and deviation taken over the whole sample."""

    lookback: int = 20
    name: str = "leak_full_sample_zscore"

    def compute(self, data: MarketData) -> pd.DataFrame:
        momentum = data.closes.pct_change(self.lookback)
        return (momentum - momentum.mean()) / momentum.std()


@dataclass(frozen=True)
class CenteredWindowSignal:
    """Smooths returns with a window centred on today, so it includes later days."""

    window: int = 5
    name: str = "leak_centered_window"

    def compute(self, data: MarketData) -> pd.DataFrame:
        return data.closes.pct_change().rolling(self.window, center=True).mean()


@dataclass(frozen=True)
class BackfillSignal:
    """Samples a feature weekly and back-fills the gaps with the next reading."""

    step: int = 5
    name: str = "leak_backfill"

    def compute(self, data: MarketData) -> pd.DataFrame:
        momentum = data.closes.pct_change(self.step)
        keep = np.arange(len(momentum)) % self.step == self.step - 1
        return momentum.where(pd.Series(keep, index=momentum.index), axis=0).bfill()


@dataclass(frozen=True)
class EventTimeBucketSignal:
    """Counts documents on the day they happened, even if they were seen later."""

    short_window: int = 5
    long_window: int = 60
    name: str = "leak_event_time_bucket"

    def compute(self, data: MarketData) -> pd.DataFrame:
        log_counts = document_counts(data, by="event_time").apply(np.log1p)
        recent = log_counts.rolling(self.short_window).mean()
        usual = log_counts.rolling(self.long_window, min_periods=self.long_window // 3).mean()
        return recent - usual


@dataclass(frozen=True)
class ArchivedEngagementSignal:
    """Engagement signal that reads each post's final, archived score.

    Social-media studies often take engagement (score, comment count) from
    archives. Archives such as Arctic Shift overwrite a post's score with a
    value fetched later, often about 36 hours after posting, and engagement
    keeps growing in reaction to the price moves that follow. A backtest that
    puts that value on the day of the post trades on returns it could not yet
    have seen. Identical to ``EngagementSignal`` except for which snapshot it
    reads.
    """

    name: str = "leak_archived_engagement"

    def compute(self, data: MarketData) -> pd.DataFrame:
        return engagement_scores(data, snapshot="final")


def planted_leaks() -> list[Signal]:
    return [
        PeekAheadSignal(),
        FullSampleZScoreSignal(),
        CenteredWindowSignal(),
        BackfillSignal(),
        EventTimeBucketSignal(),
        ArchivedEngagementSignal(),
    ]
