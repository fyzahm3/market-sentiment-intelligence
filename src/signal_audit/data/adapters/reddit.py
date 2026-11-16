"""Reddit posts via the official Data API (OAuth, app-only).

Requires an approved app (https://www.reddit.com/prefs/apps). Only ticker-level
metadata is kept; titles, bodies and author names are read for ticker tagging
and then discarded.

Status: exercised against a mocked transport only. Not yet run against the
live API.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
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


class RedditClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        user_agent: str,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 20.0,
    ) -> None:
        self._auth = (client_id, client_secret)
        self._http = httpx.Client(
            headers={"User-Agent": user_agent}, transport=transport, timeout=timeout
        )
        self._token: str | None = None

    def close(self) -> None:
        self._http.close()

    def _access_token(self) -> str:
        if self._token is None:
            response = self._http.post(
                TOKEN_URL, auth=self._auth, data={"grant_type": "client_credentials"}
            )
            response.raise_for_status()
            self._token = str(response.json()["access_token"])
        return self._token

    def fetch_new(self, subreddit: str, limit: int = 100) -> list[dict[str, Any]]:
        """The newest posts in ``subreddit`` (at most 100 per call)."""
        response = self._http.get(
            f"{API_BASE}/r/{subreddit}/new",
            params={"limit": min(limit, 100), "raw_json": 1},
            headers={"Authorization": f"Bearer {self._access_token()}"},
        )
        response.raise_for_status()
        children = response.json()["data"]["children"]
        return [child["data"] for child in children]


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
