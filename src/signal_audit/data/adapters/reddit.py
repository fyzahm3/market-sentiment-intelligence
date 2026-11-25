"""Reddit posts via the official Data API (OAuth, app-only).

Requires an approved app (https://www.reddit.com/prefs/apps). Only ticker-level
metadata is kept; titles, bodies and author names are read for ticker tagging
and then discarded.

Status: exercised against a mocked transport only. Not yet run against the
live API. Only the official API is used, within the free limit of 100 queries
per minute.
"""

from __future__ import annotations

import re
import time
from collections import deque
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any

import httpx
import pandas as pd

TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
API_BASE = "https://oauth.reddit.com"

_CASHTAG = re.compile(r"(?<![A-Za-z0-9])\$([A-Z]{1,5})\b")
_BARE_WORD = re.compile(r"\b[A-Z]{3,5}\b")


def extract_tickers(text: str, universe: Iterable[str]) -> set[str]:
    """Tickers from ``universe`` mentioned in ``text``.

    Cashtags (``$AAPL``) always count. Bare upper-case words count only when
    they are three or more letters, to limit false matches on words like "A" or
    "IT". Precision and recall are to be measured in milestone M2.
    """
    allowed = set(universe)
    found = set(_CASHTAG.findall(text)) | set(_BARE_WORD.findall(text))
    return found & allowed


class RedditAPIError(RuntimeError):
    """Reddit kept failing after the bounded retries were used up."""


def _float_header(response: httpx.Response, name: str) -> float | None:
    raw = response.headers.get(name)
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _fullname(identifier: str) -> str:
    return identifier if identifier.startswith("t3_") else f"t3_{identifier}"


class RedditClient:
    """Application-only OAuth client for the two read endpoints the collector needs.

    Rate limiting: a sliding window never lets more than ``max_per_minute``
    requests start in any 60 seconds (Reddit's free limit is 100), and the
    ``X-Ratelimit-*`` headers are honoured: when ``Remaining`` hits zero the
    client sleeps until ``Reset``. HTTP 429, 5xx and transport errors are
    retried with deterministic exponential backoff, at most ``max_retries``
    times, and then raised. ``clock`` (epoch seconds) and ``sleeper`` are
    injectable so tests never wait.
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        user_agent: str,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 20.0,
        clock: Callable[[], float] = time.time,
        sleeper: Callable[[float], None] = time.sleep,
        max_per_minute: int = 90,
        max_retries: int = 4,
        backoff_seconds: float = 2.0,
        token_margin_seconds: float = 60.0,
    ) -> None:
        if not 1 <= max_per_minute <= 100:
            raise ValueError("max_per_minute must be between 1 and 100")
        self._auth = (client_id, client_secret)
        self._http = httpx.Client(
            headers={"User-Agent": user_agent}, transport=transport, timeout=timeout
        )
        self._clock = clock
        self._sleep = sleeper
        self._max_per_minute = max_per_minute
        self._max_retries = max_retries
        self._backoff = backoff_seconds
        self._margin = token_margin_seconds
        self._token: str | None = None
        self._token_expiry = 0.0
        self._window: deque[float] = deque()
        self._remaining: float | None = None
        self._reset_at = 0.0
        self.api_calls = 0
        self.token_requests = 0

    def close(self) -> None:
        self._http.close()

    def _access_token(self) -> str:
        if self._token is None or self._clock() >= self._token_expiry - self._margin:
            self.token_requests += 1
            response = self._http.post(
                TOKEN_URL, auth=self._auth, data={"grant_type": "client_credentials"}
            )
            response.raise_for_status()
            body = response.json()
            self._token = str(body["access_token"])
            self._token_expiry = self._clock() + float(body.get("expires_in", 3600))
        return self._token

    def _throttle(self) -> None:
        now = self._clock()
        if self._remaining is not None and self._remaining <= 1 and now < self._reset_at:
            self._sleep(self._reset_at - now)
            self._remaining = None
        now = self._clock()
        while self._window and now - self._window[0] >= 60.0:
            self._window.popleft()
        if len(self._window) >= self._max_per_minute:
            self._sleep(self._window[0] + 60.0 - now)
            now = self._clock()
            while self._window and now - self._window[0] >= 60.0:
                self._window.popleft()
        self._window.append(self._clock())

    def _note_limits(self, response: httpx.Response) -> None:
        remaining = _float_header(response, "X-Ratelimit-Remaining")
        reset = _float_header(response, "X-Ratelimit-Reset")
        if remaining is not None:
            self._remaining = remaining
        if reset is not None:
            self._reset_at = self._clock() + reset

    def _get(self, path: str, params: Mapping[str, Any]) -> dict[str, Any]:
        reauthenticated = False
        attempt = 0
        while True:
            self._throttle()
            self.api_calls += 1
            try:
                response = self._http.get(
                    f"{API_BASE}{path}",
                    params=dict(params),
                    headers={"Authorization": f"Bearer {self._access_token()}"},
                )
            except httpx.TransportError:
                if attempt >= self._max_retries:
                    raise
                self._sleep(self._backoff * 2**attempt)
                attempt += 1
                continue
            self._note_limits(response)
            if response.status_code == 401 and not reauthenticated:
                reauthenticated = True
                self._token = None
                continue
            if response.status_code == 429 or response.status_code >= 500:
                if attempt >= self._max_retries:
                    raise RedditAPIError(
                        f"{path} still returning {response.status_code} after "
                        f"{self._max_retries} retries"
                    )
                wait = self._backoff * 2**attempt
                if response.status_code == 429:
                    hinted = _float_header(response, "Retry-After")
                    if hinted is None:
                        hinted = _float_header(response, "X-Ratelimit-Reset")
                    wait = max(wait, hinted or 0.0)
                self._sleep(wait)
                attempt += 1
                continue
            response.raise_for_status()
            return dict(response.json())

    def fetch_new(
        self,
        subreddit: str,
        limit: int = 100,
        *,
        after: str | None = None,
        before: str | None = None,
    ) -> list[dict[str, Any]]:
        """The newest posts in ``subreddit`` (at most 100 per call).

        ``after``/``before`` are fullnames (``t3_xxxx``) for paging.
        """
        params: dict[str, Any] = {"limit": min(limit, 100), "raw_json": 1}
        if after is not None:
            params["after"] = _fullname(after)
        if before is not None:
            params["before"] = _fullname(before)
        body = self._get(f"/r/{subreddit}/new", params)
        return [child["data"] for child in body["data"]["children"]]

    def fetch_info(self, fullnames: Sequence[str]) -> list[dict[str, Any]]:
        """Current state of posts by id or ``t3_`` fullname, 100 per request."""
        names = [_fullname(name) for name in fullnames]
        posts: list[dict[str, Any]] = []
        for start in range(0, len(names), 100):
            batch = names[start : start + 100]
            body = self._get("/api/info", {"id": ",".join(batch), "raw_json": 1})
            posts.extend(child["data"] for child in body["data"]["children"])
        return posts


def posts_to_frame(
    posts: Sequence[Mapping[str, Any]], universe: Iterable[str], fetched_at: pd.Timestamp
) -> pd.DataFrame:
    """One row per (post, ticker), ready for ``PointInTimeStore``.

    ``knowledge_time`` is the fetch time: that is when this system first saw
    the post, whatever its creation time.
    """
    if fetched_at.tzinfo is None:
        raise ValueError("fetched_at must be timezone-aware")
    fetched_at = fetched_at.tz_convert("UTC")
    allowed = set(universe)

    rows: list[dict[str, Any]] = []
    for post in posts:
        text = f"{post.get('title', '')} {post.get('selftext', '')}"
        event_time = pd.Timestamp(float(post["created_utc"]), unit="s", tz="UTC")
        for ticker in sorted(extract_tickers(text, allowed)):
            rows.append(
                {
                    "ticker": ticker,
                    "event_time": event_time,
                    "knowledge_time": max(fetched_at, event_time),
                    "post_id": str(post["id"]),
                    "subreddit": str(post.get("subreddit", "")),
                    "score": int(post.get("score", 0)),
                    "num_comments": int(post.get("num_comments", 0)),
                }
            )

    frame = pd.DataFrame(
        rows,
        columns=[
            "ticker",
            "event_time",
            "knowledge_time",
            "post_id",
            "subreddit",
            "score",
            "num_comments",
        ],
    )
    for column in ("event_time", "knowledge_time"):
        frame[column] = pd.to_datetime(frame[column], utc=True)
    return frame
