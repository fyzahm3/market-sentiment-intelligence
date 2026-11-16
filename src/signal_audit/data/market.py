"""The dataset a signal is computed from: daily prices plus optional documents."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from signal_audit.data.pit import PointInTimeStore
from signal_audit.sessions import session_close_utc


@dataclass(frozen=True)
class MarketData:
    """Daily open and close prices (dates x tickers) and point-in-time documents.

    ``opens`` and ``closes`` share a sorted, unique, tz-naive ``DatetimeIndex`` of
    session dates and the same ticker columns.
    """

    opens: pd.DataFrame
    closes: pd.DataFrame
    documents: PointInTimeStore | None = None

    def __post_init__(self) -> None:
        index = self.opens.index
        if not isinstance(index, pd.DatetimeIndex):
            raise ValueError("prices must be indexed by a DatetimeIndex")
        if index.tz is not None:
            raise ValueError("price dates must be timezone-naive session dates")
        if not index.is_monotonic_increasing or not index.is_unique:
            raise ValueError("price dates must be sorted and unique")
        if not index.equals(self.closes.index):
            raise ValueError("opens and closes must share the same dates")
        if list(self.opens.columns) != list(self.closes.columns):
            raise ValueError("opens and closes must share the same tickers")

    @property
    def dates(self) -> pd.DatetimeIndex:
        index = self.opens.index
        assert isinstance(index, pd.DatetimeIndex)
        return index

    @property
    def tickers(self) -> list[str]:
        return [str(c) for c in self.opens.columns]

    def truncate(self, cut: pd.Timestamp) -> MarketData:
        """Everything knowable at the close of session ``cut``.

        Prices after ``cut`` are dropped, and documents are limited to those
        with ``knowledge_time`` at or before that session's close.
        """
        documents = None
        if self.documents is not None:
            documents = self.documents.truncate(session_close_utc(cut))
        return MarketData(
            opens=self.opens.loc[:cut], closes=self.closes.loc[:cut], documents=documents
        )
