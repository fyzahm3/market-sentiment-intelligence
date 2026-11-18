from __future__ import annotations

import httpx
import numpy as np
import pandas as pd
import pytest

from signal_audit.data.adapters.prices import frame_to_market
from signal_audit.data.adapters.reddit import (
    API_BASE,
    TOKEN_URL,
    RedditAPIError,
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


class _Clock:
    """A fake clock whose sleeper advances time instead of waiting."""

    def __init__(self) -> None:
        self.now = 1_000.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class _Server:
    """Counts token and data requests; ``script`` holds forced data responses."""

    def __init__(self, script: list[httpx.Response] | None = None, expires_in: int = 3600) -> None:
        self.tokens = 0
        self.expires_in = expires_in
        self.script = list(script or [])
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if str(request.url) == TOKEN_URL:
            assert request.content == b"grant_type=client_credentials"
            self.tokens += 1
            return httpx.Response(
                200, json={"access_token": f"tok-{self.tokens}", "expires_in": self.expires_in}
            )
        self.requests.append(request)
        if self.script:
            return self.script.pop(0)
        return httpx.Response(200, json={"data": {"children": []}})


def _client(server: _Server, clock: _Clock, **kwargs: float) -> RedditClient:
    return RedditClient(
        "id",
        "secret",
        "test-agent",
        transport=httpx.MockTransport(server),
        clock=clock,
        sleeper=clock.sleep,
        **kwargs,  # type: ignore[arg-type]
    )


def test_token_is_fetched_once_and_reused() -> None:
    server, clock = _Server(), _Clock()
    client = _client(server, clock)
    client.fetch_new("stocks")
    client.fetch_new("stocks")
    assert server.tokens == 1
    assert {r.headers["authorization"] for r in server.requests} == {"Bearer tok-1"}


def test_token_is_refreshed_shortly_before_expiry() -> None:
    server, clock = _Server(expires_in=600), _Clock()
    client = _client(server, clock)
    client.fetch_new("stocks")
    clock.now += 500  # still more than the 60 s margin left
    client.fetch_new("stocks")
    assert server.tokens == 1
    clock.now += 50  # now inside the margin
    client.fetch_new("stocks")
    assert server.tokens == 2


def test_401_reauthenticates_once() -> None:
    ok = httpx.Response(200, json={"data": {"children": []}})
    server, clock = _Server([httpx.Response(401), ok]), _Clock()
    client = _client(server, clock)
    assert client.fetch_new("stocks") == []
    assert server.tokens == 2
    assert server.requests[-1].headers["authorization"] == "Bearer tok-2"


def test_repeated_401_raises() -> None:
    server, clock = _Server([httpx.Response(401), httpx.Response(401)]), _Clock()
    with pytest.raises(httpx.HTTPStatusError):
        _client(server, clock).fetch_new("stocks")
    assert server.tokens == 2


def test_429_backs_off_then_succeeds() -> None:
    ok = httpx.Response(200, json={"data": {"children": []}})
    limited = httpx.Response(429, headers={"Retry-After": "10"})
    server, clock = _Server([limited, httpx.Response(503), ok]), _Clock()
    assert _client(server, clock, backoff_seconds=2.0).fetch_new("stocks") == []
    assert clock.sleeps == [10.0, 4.0]


def test_retries_are_bounded() -> None:
    server, clock = _Server([httpx.Response(500)] * 10), _Clock()
    client = _client(server, clock, max_retries=2)
    with pytest.raises(RedditAPIError):
        client.fetch_new("stocks")
    assert len(server.requests) == 3


def test_fetch_info_batches_at_100() -> None:
    def info(request: httpx.Request) -> httpx.Response:
        ids = request.url.params["id"].split(",")
        children = [{"data": {"id": name[3:]}} for name in ids]
        return httpx.Response(200, json={"data": {"children": children}})

    clock = _Clock()
    server = _Server()
    inner = httpx.MockTransport(lambda r: info(r) if r.url.path == "/api/info" else server(r))
    client = RedditClient("id", "secret", "ua", transport=inner, clock=clock, sleeper=clock.sleep)
    posts = client.fetch_info([f"p{i}" for i in range(250)])
    assert [p["id"] for p in posts] == [f"p{i}" for i in range(250)]
    assert client.api_calls == 3


def test_ratelimit_headers_pause_until_reset() -> None:
    empty = {"data": {"children": []}}
    drained = httpx.Response(
        200, json=empty, headers={"X-Ratelimit-Remaining": "0", "X-Ratelimit-Reset": "30"}
    )
    server, clock = _Server([drained, httpx.Response(200, json=empty)]), _Clock()
    client = _client(server, clock)
    client.fetch_new("stocks")
    assert clock.sleeps == []
    client.fetch_new("stocks")
    assert clock.sleeps == [30.0]


def test_client_never_exceeds_requests_per_minute() -> None:
    server, clock = _Server(), _Clock()
    client = _client(server, clock, max_per_minute=5)
    started: list[float] = []
    for _ in range(12):
        client.fetch_new("stocks")
        started.append(clock.now)
    for i, when in enumerate(started):
        in_window = [t for t in started[: i + 1] if when - t < 60.0]
        assert len(in_window) <= 5
    assert clock.sleeps  # it really had to wait
