"""Seeded synthetic market data for demos and tests.

The generator plants a known, tradable effect so the audit can be checked
against ground truth: a persistent latent "attention" factor per ticker drives
both the number of documents on day T and the open-to-open return earned by a
position entered at the open of T+1. A signal that counts documents honestly
therefore has a real edge. Because the factor is persistent, prices trend
slightly, so momentum has a weak indirect edge. Random scores have none.

Some documents arrive late (their ``knowledge_time`` is days after their
``event_time``), which is what makes event-time bucketing a detectable leak.

This data says nothing about real markets.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from signal_audit.data.market import MarketData
from signal_audit.data.pit import PointInTimeStore
from signal_audit.sessions import session_opens_utc

DEFAULT_TICKERS = ("AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG", "HHH")


def synthetic_market(
    n_days: int = 750,
    tickers: tuple[str, ...] = DEFAULT_TICKERS,
    seed: int = 7,
    start: str = "2021-01-04",
    beta: float = 0.003,
    noise: float = 0.015,
    persistence: float = 0.9,
    docs_per_day: float = 6.0,
    late_fraction: float = 0.2,
) -> MarketData:
    """Build a synthetic market with a planted attention effect.

    ``beta`` is the daily return per unit of the latent factor; set it to 0 for
    a market with no exploitable structure at all.
    """
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start, periods=n_days)
    n_tickers = len(tickers)

    # Persistent latent factor (AR(1), unit variance).
    shocks = rng.standard_normal((n_days, n_tickers))
    latent = np.empty_like(shocks)
    latent[0] = shocks[0]
    scale = np.sqrt(1.0 - persistence**2)
    for t in range(1, n_days):
        latent[t] = persistence * latent[t - 1] + scale * shocks[t]

    # open_to_open[t] is the return from the open of t to the open of t+1.
    # A decision at the close of t is filled at the open of t+1 and earns
    # open_to_open[t+1], so that is where latent[t] shows up.
    open_to_open = rng.normal(0.0, noise, (n_days, n_tickers))
    open_to_open[1:] += beta * latent[:-1]

    growth = np.vstack([np.ones((1, n_tickers)), 1.0 + open_to_open[:-1]])
    opens = 100.0 * np.cumprod(growth, axis=0)
    closes = opens * (1.0 + rng.normal(0.0, noise * 0.6, (n_days, n_tickers)))

    documents = _synthetic_documents(rng, dates, tickers, latent, docs_per_day, late_fraction)
    return MarketData(
        opens=pd.DataFrame(opens, index=dates, columns=list(tickers)),
        closes=pd.DataFrame(closes, index=dates, columns=list(tickers)),
        documents=documents,
    )


def _synthetic_documents(
    rng: np.random.Generator,
    dates: pd.DatetimeIndex,
    tickers: tuple[str, ...],
    latent: np.ndarray,
    docs_per_day: float,
    late_fraction: float,
) -> PointInTimeStore:
    counts = rng.poisson(docs_per_day * np.exp(0.5 * latent))
    day_idx, ticker_idx = np.nonzero(counts)
    repeats = counts[day_idx, ticker_idx]
    day_idx = np.repeat(day_idx, repeats)
    ticker_idx = np.repeat(ticker_idx, repeats)
    n_docs = len(day_idx)

    # Posted during the session, comfortably before the close.
    opens_utc = session_opens_utc(dates)
    offset_s = rng.uniform(0, 6 * 3600, n_docs)
    event_time = opens_utc[day_idx] + pd.to_timedelta(offset_s, unit="s")

    # Most documents are seen within minutes; some only arrive days later.
    late = rng.random(n_docs) < late_fraction
    delay_s = np.where(
        late, rng.uniform(1 * 86400, 3 * 86400, n_docs), rng.uniform(0, 20 * 60, n_docs)
    )
    knowledge_time = event_time + pd.to_timedelta(delay_s, unit="s")

    frame = pd.DataFrame(
        {
            "ticker": np.asarray(tickers, dtype=object)[ticker_idx],
            "event_time": event_time,
            "knowledge_time": knowledge_time,
        }
    )
    return PointInTimeStore(frame)
