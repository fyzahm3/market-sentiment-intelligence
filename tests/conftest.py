from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from signal_audit.data.market import MarketData
from signal_audit.data.synthetic import synthetic_market
from signal_audit.sessions import sessions_between


@pytest.fixture(scope="session")
def market() -> MarketData:
    """Synthetic market with the planted attention effect."""
    return synthetic_market(n_days=400, seed=11)


@pytest.fixture(scope="session")
def flat_market() -> MarketData:
    """Synthetic market with no exploitable structure."""
    return synthetic_market(n_days=400, seed=11, beta=0.0)


def constant_prices(n_days: int = 10, tickers: tuple[str, ...] = ("A", "B", "C")) -> MarketData:
    dates = pd.bdate_range("2024-01-01", periods=n_days)
    frame = pd.DataFrame(100.0, index=dates, columns=list(tickers))
    return MarketData(opens=frame.copy(), closes=frame.copy())


def session_prices(last: dt.date, n_days: int = 80, seed: int = 5) -> MarketData:
    """Synthetic prices re-indexed onto the ``n_days`` NYSE sessions ending at ``last``."""
    market = synthetic_market(n_days=n_days, seed=seed, engagement=False)
    dates = sessions_between(last - dt.timedelta(days=3 * n_days), last)[-n_days:]
    assert len(dates) == n_days
    return MarketData(
        opens=market.opens.set_axis(dates, axis=0), closes=market.closes.set_axis(dates, axis=0)
    )
