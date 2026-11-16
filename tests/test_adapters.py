from __future__ import annotations

import httpx
import numpy as np
import pandas as pd
import pytest

from signal_audit.data.adapters.prices import frame_to_market
from signal_audit.data.adapters.reddit import (
    API_BASE,
    TOKEN_URL,
    RedditClient,
    extract_tickers,
    posts_to_frame,
)
from signal_audit.data.pit import PointInTimeStore

UNIVERSE = ["AAPL", "TSLA", "NVDA", "A"]


def test_extract_tickers_cashtags_and_bare_words() -> None:
    text = "Loading up on $TSLA and NVDA. A great day. $ZZZZ is not tracked, nor is aapl."
    assert extract_tickers(text, UNIVERSE) == {"TSLA", "NVDA"}


def test_extract_tickers_short_symbols_need_a_cashtag() -> None:
    assert extract_tickers("A stock I like", UNIVERSE) == set()
    assert extract_tickers("I like $A", UNIVERSE) == {"A"}


def _handler(request: httpx.Request) -> httpx.Response:
    if str(request.url) == TOKEN_URL:
        assert request.headers["authorization"].startswith("Basic ")
        return httpx.Response(200, json={"access_token": "token-123"})
    assert str(request.url).startswith(f"{API_BASE}/r/stocks/new")
    assert request.headers["authorization"] == "Bearer token-123"
    assert request.headers["user-agent"] == "test-agent"
    return httpx.Response(
        200,
        json={
            "data": {
                "children": [
                    {
                        "data": {
                            "id": "abc",
                            "title": "$AAPL earnings",
                            "selftext": "also watching TSLA",
                            "created_utc": 1_704_724_200.0,
                            "subreddit": "stocks",
                            "score": 42,
                            "num_comments": 7,
                        }
                    },
                    {
                        "data": {
                            "id": "def",
                            "title": "no tickers here",
                            "selftext": "",
                            "created_utc": 1_704_724_300.0,
                        }
                    },
                ]
            }
        },
    )


def test_reddit_client_fetches_with_bearer_token() -> None:
    client = RedditClient("id", "secret", "test-agent", transport=httpx.MockTransport(_handler))
    posts = client.fetch_new("stocks")
    client.close()
    assert [post["id"] for post in posts] == ["abc", "def"]


def test_posts_to_frame_uses_fetch_time_as_knowledge_time() -> None:
    client = RedditClient("id", "secret", "test-agent", transport=httpx.MockTransport(_handler))
    posts = client.fetch_new("stocks")
    client.close()

    fetched_at = pd.Timestamp("2024-01-08 15:00", tz="UTC")
    frame = posts_to_frame(posts, UNIVERSE, fetched_at)

    assert sorted(frame["ticker"]) == ["AAPL", "TSLA"]
    assert (frame["knowledge_time"] == fetched_at).all()
    assert (frame["event_time"] < frame["knowledge_time"]).all()
    assert "title" not in frame.columns and "author" not in frame.columns
    assert len(PointInTimeStore(frame)) == 2


def test_posts_to_frame_handles_no_matches() -> None:
    frame = posts_to_frame([], UNIVERSE, pd.Timestamp("2024-01-08", tz="UTC"))
    assert len(PointInTimeStore(frame)) == 0


def test_posts_to_frame_requires_aware_fetch_time() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        posts_to_frame([], UNIVERSE, pd.Timestamp("2024-01-08"))


def _download(tickers: list[str]) -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-01", periods=4)
    columns = pd.MultiIndex.from_product([["Close", "Open"], tickers])
    values = np.arange(len(dates) * len(columns), dtype=float).reshape(len(dates), -1) + 1.0
    return pd.DataFrame(values, index=dates, columns=columns)


def test_frame_to_market_splits_fields() -> None:
    data = frame_to_market(_download(["AAPL", "TSLA"]), ["AAPL", "TSLA"])
    assert data.tickers == ["AAPL", "TSLA"]
    assert len(data.dates) == 4
    assert data.opens.loc[data.dates[0], "AAPL"] == 3.0
    assert data.closes.loc[data.dates[0], "AAPL"] == 1.0


def test_frame_to_market_reports_missing_tickers() -> None:
    with pytest.raises(ValueError, match="no price data returned"):
        frame_to_market(_download(["AAPL"]), ["AAPL", "TSLA"])
