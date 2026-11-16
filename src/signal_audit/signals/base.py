"""The interface every auditable signal implements."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import pandas as pd

from signal_audit.data.market import MarketData
from signal_audit.sessions import assign_sessions


@runtime_checkable
class Signal(Protocol):
    """Turns market data into a score per ticker per day.

    ``compute`` returns a frame indexed by session date with one column per
    ticker. Higher means more bullish; NaN means no opinion. The row for date T
    may depend only on data known by the close of T. The truncation test in
    ``signal_audit.audit.leakage`` checks that this holds.
    """

    @property
    def name(self) -> str: ...

    def compute(self, data: MarketData) -> pd.DataFrame: ...


def align_scores(scores: pd.DataFrame, data: MarketData) -> pd.DataFrame:
    """Reindex scores onto the dataset's dates and tickers."""
    return scores.reindex(index=data.dates, columns=data.tickers).astype(float)


def document_counts(data: MarketData, *, by: str = "knowledge_time") -> pd.DataFrame:
    """Documents per ticker per session.

    With ``by="knowledge_time"`` (the honest choice) a document counts toward
    the first session whose close is at or after the moment it became known.
    ``by="event_time"`` assigns it by when it happened instead, which uses
    information that may not have been available yet.
    """
    counts = pd.DataFrame(0.0, index=data.dates, columns=data.tickers)
    if data.documents is None or len(data.documents) == 0:
        return counts

    frame = data.documents.frame
    position = assign_sessions(frame[by], data.dates)
    in_range = position < len(data.dates)
    frame = frame[in_range]
    frame = frame.assign(session=data.dates[position[in_range]])
    frame = frame[frame["ticker"].isin(data.tickers)]

    table = frame.groupby(["session", "ticker"]).size().unstack(fill_value=0)
    return counts.add(table.reindex(index=data.dates, columns=data.tickers), fill_value=0.0)
