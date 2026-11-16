"""Daily price loader backed by yfinance (optional dependency).

yfinance is an unofficial client. Treat its output as unverified until the
sanity checks planned for milestone M1 are in place.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

import pandas as pd

from signal_audit.data.market import MarketData


def frame_to_market(raw: pd.DataFrame, tickers: Sequence[str]) -> MarketData:
    """Convert a yfinance-style download (field x ticker columns) to MarketData."""
    if not isinstance(raw.columns, pd.MultiIndex):
        raise ValueError("expected columns indexed by (field, ticker)")

    opens = cast(pd.DataFrame, raw["Open"]).reindex(columns=list(tickers))
    closes = cast(pd.DataFrame, raw["Close"]).reindex(columns=list(tickers))

    empty = [t for t in tickers if opens[t].isna().all()]
    if empty:
        raise ValueError(f"no price data returned for: {empty}")

    keep = ~(opens.isna().all(axis=1) | closes.isna().all(axis=1))
    opens, closes = opens[keep], closes[keep]

    index = pd.DatetimeIndex(opens.index)
    if index.tz is not None:
        index = index.tz_localize(None)
    index = index.normalize()
    opens.index = index
    closes.index = index
    return MarketData(opens=opens.sort_index(), closes=closes.sort_index())


def load_prices(tickers: Sequence[str], start: str, end: str) -> MarketData:
    """Download split- and dividend-adjusted daily prices."""
    try:
        import yfinance as yf
    except ImportError as exc:
        raise RuntimeError(
            "yfinance is not installed. Install the data extra: uv sync --extra data"
        ) from exc

    raw = yf.download(
        list(tickers),
        start=start,
        end=end,
        auto_adjust=True,
        progress=False,
        group_by="column",
        multi_level_index=True,
    )
    if raw is None or raw.empty:
        raise RuntimeError("price download returned no rows")
    return frame_to_market(raw, tickers)
