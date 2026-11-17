from __future__ import annotations

import pandas as pd

from signal_audit.data.market import MarketData
from signal_audit.sessions import session_close_utc
from tests.conftest import constant_prices


def test_truncate_drops_later_engagement_snapshots(market: MarketData) -> None:
    assert market.engagement is not None
    cut = market.dates[200]
    close = session_close_utc(cut)

    truncated = market.truncate(cut)

    assert truncated.engagement is not None
    kept = truncated.engagement.frame
    full = market.engagement.frame
    assert len(kept) == int((full["knowledge_time"] <= close).sum())
    assert 0 < len(kept) < len(full)
    assert (kept["knowledge_time"] <= close).all()
    # A post can survive with only its earlier snapshots.
    later = full[full["knowledge_time"] > close]
    assert set(later["post_id"]) & set(kept["post_id"])


def test_truncate_without_engagement_keeps_none() -> None:
    data = constant_prices(n_days=5)
    truncated = data.truncate(pd.Timestamp(data.dates[2]))
    assert truncated.engagement is None
    assert truncated.documents is None
    assert len(truncated.dates) == 3
