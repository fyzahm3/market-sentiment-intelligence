"""Honest reference signals. Each one passes the truncation test."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from signal_audit.data.market import MarketData
from signal_audit.signals.base import Signal, document_counts


@dataclass(frozen=True)
class MomentumSignal:
    """Trailing close-to-close return over ``lookback`` sessions."""

    lookback: int = 20
    name: str = "momentum"

    def compute(self, data: MarketData) -> pd.DataFrame:
        return data.closes.pct_change(self.lookback)


@dataclass(frozen=True)
class RandomSignal:
    """Pure noise. The score for a date depends only on the seed and that date."""

    seed: int = 0
    name: str = "random"

    def compute(self, data: MarketData) -> pd.DataFrame:
        rows = [
            np.random.default_rng([self.seed, date.toordinal()]).standard_normal(len(data.tickers))
            for date in data.dates
        ]
        return pd.DataFrame(rows, index=data.dates, columns=data.tickers)


@dataclass(frozen=True)
class MentionSpikeSignal:
    """Recent document volume relative to its own longer-run level.

    Documents are counted by ``knowledge_time``, so a post only counts once
    this system could have seen it.
    """

    short_window: int = 5
    long_window: int = 60
    name: str = "mention_spike"

    def compute(self, data: MarketData) -> pd.DataFrame:
        log_counts = document_counts(data, by="knowledge_time").apply(np.log1p)
        recent = log_counts.rolling(self.short_window).mean()
        usual = log_counts.rolling(self.long_window, min_periods=self.long_window // 3).mean()
        return recent - usual


def honest_signals() -> list[Signal]:
    return [MomentumSignal(), RandomSignal(), MentionSpikeSignal()]
