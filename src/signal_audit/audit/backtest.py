"""Turns scores into portfolio returns under one fixed convention.

* A score for date T is known at the close of T.
* The resulting position is entered at the open of T+1.
* It earns the open-to-open return from T+1 to T+2.
* Costs are charged on turnover whenever weights change.

Signals never choose their own fill price. This is the only module that
converts scores into returns.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from signal_audit.data.market import MarketData
from signal_audit.signals.base import align_scores


@dataclass(frozen=True)
class BacktestConfig:
    top_k: int = 3
    cost_bps: float = 10.0

    def __post_init__(self) -> None:
        if self.top_k < 1:
            raise ValueError("top_k must be at least 1")
        if self.cost_bps < 0:
            raise ValueError("cost_bps cannot be negative")


@dataclass(frozen=True)
class BacktestResult:
    returns: pd.Series  # net of costs, indexed by the session the position was entered
    gross_returns: pd.Series
    turnover: pd.Series
    weights: pd.DataFrame  # weights held during each session


def target_weights(scores: pd.DataFrame, top_k: int) -> pd.DataFrame:
    """Long-only: 1/top_k in each of the top_k scored tickers, the rest in cash.

    If fewer than top_k tickers have a score, the remainder stays in cash rather
    than being concentrated into the names that do.
    """
    ranks = scores.rank(axis=1, ascending=False, method="first")
    return (ranks <= top_k).astype(float) / top_k


def open_to_open_returns(data: MarketData) -> pd.DataFrame:
    """Return from the open of each session to the open of the next."""
    return data.opens.shift(-1) / data.opens - 1.0


def run_backtest(scores: pd.DataFrame, data: MarketData, config: BacktestConfig) -> BacktestResult:
    scores = align_scores(scores, data)
    decided = target_weights(scores, config.top_k)

    # Weights decided at the close of T are held from the open of T+1.
    held = decided.shift(1).fillna(0.0)
    forward = open_to_open_returns(data)

    gross = (held * forward.fillna(0.0)).sum(axis=1)
    turnover = held.diff().abs().sum(axis=1)
    turnover.iloc[0] = held.iloc[0].abs().sum()
    net = gross - turnover * config.cost_bps / 10_000.0

    # The final session has no next open, so its return is unknown.
    keep = slice(0, len(net) - 1)
    return BacktestResult(
        returns=net.iloc[keep],
        gross_returns=gross.iloc[keep],
        turnover=turnover.iloc[keep],
        weights=held.iloc[keep],
    )
