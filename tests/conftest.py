from __future__ import annotations

import pandas as pd
import pytest

from signal_audit.data.market import MarketData
from signal_audit.data.synthetic import synthetic_market


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
