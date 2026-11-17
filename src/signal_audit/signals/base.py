"""The interface every auditable signal implements."""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

import numpy as np
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


def engagement_scores(
    data: MarketData, *, snapshot: Literal["visible", "final"] = "visible"
) -> pd.DataFrame:
    """Summed ``log1p`` engagement of the posts assigned to each session.

    A post belongs to the session of its first snapshot, the first session
    whose close is at or after the moment the post became known. With
    ``snapshot="visible"`` (the honest choice) each post contributes its latest
    snapshot fetched by that session's close. ``snapshot="final"`` uses its
    last snapshot overall instead, which is what an archive stores and which
    can be fetched days later.

    Sessions without posts score 0. Without engagement data every score is NaN.
    """
    if data.engagement is None:
        return pd.DataFrame(np.nan, index=data.dates, columns=data.tickers)
    totals = pd.DataFrame(0.0, index=data.dates, columns=data.tickers)
    if len(data.engagement) == 0:
        return totals

    frame = data.engagement.frame.sort_values("knowledge_time", kind="stable")
    frame = frame.assign(position=assign_sessions(frame["knowledge_time"], data.dates))
    frame = frame.assign(first=frame.groupby("post_id")["position"].transform("min"))
    frame = frame[(frame["first"] < len(data.dates)) & frame["ticker"].isin(data.tickers)]
    if snapshot == "visible":
        frame = frame[frame["position"] == frame["first"]]

    chosen = frame.groupby("post_id", sort=False).tail(1)
    chosen = chosen.assign(
        session=data.dates[chosen["first"].to_numpy()], value=np.log1p(chosen["score"])
    )
    table = chosen.groupby(["session", "ticker"])["value"].sum().unstack()
    return totals.add(table.reindex(index=data.dates, columns=data.tickers), fill_value=0.0)
