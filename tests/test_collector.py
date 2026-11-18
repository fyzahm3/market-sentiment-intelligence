from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import numpy as np
import pandas as pd
import pytest
from pydantic import SecretStr

from signal_audit.config import Settings
from signal_audit.data.adapters.reddit import TOKEN_URL, RedditClient
from signal_audit.data.collector import (
    MISSING_CREDENTIALS,
    CollectorState,
    RunSummary,
    SnapshotSchedule,
    collect_from_settings,
    load_snapshots,
    post_status,
    run_once,
)
from signal_audit.data.market import MarketData
from signal_audit.data.pit import PointInTimeStore
from signal_audit.signals.base import engagement_scores

UNIVERSE = ["AAPL", "TSLA", "NVDA"]
# Friday 15:00 New York (20:00 UTC), one hour before the session close.
FRIDAY = pd.Timestamp("2024-01-12 20:00", tz="UTC")


class FakeReddit:
    """An in-memory Reddit served through ``httpx.MockTransport``."""

    def __init__(self) -> None:
        self.posts: dict[str, dict[str, Any]] = {}
        self.info_batches: list[int] = []

    def add(
        self,
        post_id: str,
        created: pd.Timestamp,
        title: str = "$AAPL to the moon",
        subreddit: str = "stocks",
        **extra: Any,
    ) -> None:
        self.posts[post_id] = {
            "id": post_id,
            "title": title,
            "selftext": "SECRET BODY TEXT",
            "author": "someone_private",
            "created_utc": created.timestamp(),
            "subreddit": subreddit,
            "score": 1,
            "num_comments": 0,
            "upvote_ratio": 1.0,
            "removed_by_category": None,
            **extra,
        }

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if str(request.url) == TOKEN_URL:
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        path = request.url.path
        if path == "/api/info":
            ids = [name[3:] for name in request.url.params["id"].split(",")]
            self.info_batches.append(len(ids))
            found = [self.posts[i] for i in ids if i in self.posts]
            return httpx.Response(200, json=_listing(found))
        sub = path.split("/")[2]
        mine = sorted(
            (p for p in self.posts.values() if p["subreddit"] == sub),
            key=lambda p: (-p["created_utc"], p["id"]),
        )
        after = request.url.params.get("after")
        if after is not None:
            names = [f"t3_{p['id']}" for p in mine]
            mine = mine[names.index(after) + 1 :]
        return httpx.Response(200, json=_listing(mine[:100]))


def _listing(posts: list[dict[str, Any]]) -> dict[str, Any]:
    return {"data": {"children": [{"kind": "t3", "data": p} for p in posts]}}


@pytest.fixture
def reddit() -> FakeReddit:
    return FakeReddit()


def _run(
    reddit: FakeReddit, tmp_path: Path, now: pd.Timestamp, subs: tuple[str, ...] = ("stocks",)
) -> RunSummary:
    client = RedditClient(
        "id", "secret", "ua", transport=httpx.MockTransport(reddit), sleeper=lambda _s: None
    )
    try:
        return run_once(client, tmp_path / "state.json", tmp_path, subs, UNIVERSE, now)
    finally:
        client.close()


# ---------------------------------------------------------------- schedule


def test_session_close_for_weekday_and_weekend_posts() -> None:
    friday_close = pd.Timestamp("2024-01-12 21:00", tz="UTC")
    monday_close = pd.Timestamp("2024-01-15 21:00", tz="UTC")
    assert SnapshotSchedule.session_close(FRIDAY) == friday_close
    # After the Friday close, and all weekend, the post belongs to Monday's session.
    assert SnapshotSchedule.session_close(FRIDAY + pd.Timedelta(hours=2)) == monday_close
    saturday = pd.Timestamp("2024-01-13 15:00", tz="UTC")
    assert SnapshotSchedule.session_close(saturday) == monday_close


def test_targets_are_sorted_and_include_the_session_close() -> None:
    targets = SnapshotSchedule().targets(FRIDAY)
    assert [label for label, _ in targets] == ["discovery", "close", "1h", "4h", "36h", "7d"]
    assert [when for _, when in targets] == sorted(when for _, when in targets)
    assert dict(targets)["close"] == pd.Timestamp("2024-01-12 21:00", tz="UTC")


def test_advance_only_when_a_target_has_passed() -> None:
    schedule = SnapshotSchedule()
    assert schedule.advance(FRIDAY, 2, FRIDAY + pd.Timedelta(minutes=59)) is None
    assert schedule.advance(FRIDAY, 2, FRIDAY + pd.Timedelta(hours=1)) == (3, "1h")


def test_late_run_collapses_passed_targets_into_one_snapshot() -> None:
    monday = pd.Timestamp("2024-01-15 12:00", tz="UTC")
    # Discovery done (index 1); close, 1h, 4h, 36h have all passed, 7d has not.
    assert SnapshotSchedule().advance(FRIDAY, 1, monday) == (5, "36h")


# ---------------------------------------------------------------- run_once


def test_discovery_stores_tickers_but_no_text(reddit: FakeReddit, tmp_path: Path) -> None:
    reddit.add("a1", FRIDAY, title="$AAPL and TSLA")
    reddit.add("a2", FRIDAY, title="nothing to see")
    summary = _run(reddit, tmp_path, FRIDAY + pd.Timedelta(minutes=5))

    assert (summary.discovered, summary.snapshots, summary.tracking) == (1, 2, 1)
    frame = load_snapshots(tmp_path).frame
    assert sorted(frame["ticker"]) == ["AAPL", "TSLA"]
    assert set(frame["age_label"]) == {"discovery"}
    for banned in ("title", "selftext", "author", "body"):
        assert banned not in frame.columns
    stored = (tmp_path / "state.json").read_text()
    for private in ("SECRET BODY TEXT", "someone_private", "$AAPL and TSLA"):
        assert private not in stored
    files = list((tmp_path / "snapshots").glob("date=2024-01-12/part-*.parquet"))
    assert len(files) == 1


def test_state_persists_and_each_target_is_taken_once(reddit: FakeReddit, tmp_path: Path) -> None:
    reddit.add("a1", FRIDAY)
    first_time = FRIDAY + pd.Timedelta(minutes=5)
    _run(reddit, tmp_path, first_time)

    reddit.posts["a1"].update(score=50, num_comments=9, upvote_ratio=0.8)
    second_time = FRIDAY + pd.Timedelta(hours=2)
    second = _run(reddit, tmp_path, second_time)
    assert (second.discovered, second.snapshots) == (0, 1)
    assert reddit.info_batches == [1]

    again = _run(reddit, tmp_path, second_time + pd.Timedelta(minutes=10))
    assert again.snapshots == 0
    assert reddit.info_batches == [1]  # nothing due, so no /api/info call

    frame = load_snapshots(tmp_path).frame
    assert list(frame["score"]) == [1, 50]
    assert list(frame["knowledge_time"]) == [first_time, second_time]
    # Close and 1h had both passed at +2h: one row, labelled with the latest, at the real time.
    assert frame["age_label"].iloc[1] == "1h"
    assert frame["age_hours"].iloc[1] == pytest.approx(2.0)
    state = CollectorState.load(tmp_path / "state.json")
    assert state.watermarks["stocks"] == FRIDAY.timestamp()


def test_late_run_records_actual_fetch_time(reddit: FakeReddit, tmp_path: Path) -> None:
    reddit.add("a1", FRIDAY)
    _run(reddit, tmp_path, FRIDAY + pd.Timedelta(minutes=1))
    monday = pd.Timestamp("2024-01-15 12:00", tz="UTC")
    summary = _run(reddit, tmp_path, monday)
    assert summary.snapshots == 1 and summary.tracking == 1

    last = load_snapshots(tmp_path).frame.iloc[-1]
    assert last["knowledge_time"] == monday
    assert last["age_label"] == "36h"
    assert last["age_hours"] == pytest.approx(64.0)


def test_post_is_tracked_to_the_end_then_dropped(reddit: FakeReddit, tmp_path: Path) -> None:
    reddit.add("a1", FRIDAY)
    _run(reddit, tmp_path, FRIDAY)
    ages = [
        pd.Timedelta(hours=1),
        pd.Timedelta(hours=4),
        pd.Timedelta(days=3),
        pd.Timedelta(days=7, hours=1),
    ]
    summaries = [_run(reddit, tmp_path, FRIDAY + age) for age in ages]
    assert [s.snapshots for s in summaries] == [1, 1, 1, 1]
    assert summaries[-1].completed == 1 and summaries[-1].tracking == 0
    assert _run(reddit, tmp_path, FRIDAY + pd.Timedelta(days=9)).snapshots == 0


def test_deleted_and_removed_posts_are_recorded_and_still_tracked(
    reddit: FakeReddit, tmp_path: Path
) -> None:
    reddit.add("live", FRIDAY)
    reddit.add("gone", FRIDAY)
    reddit.add("mod", FRIDAY)
    _run(reddit, tmp_path, FRIDAY)

    reddit.posts["gone"].update(author="[deleted]", selftext="[deleted]")
    reddit.posts["mod"].update(removed_by_category="moderator", selftext="[removed]")
    later = FRIDAY + pd.Timedelta(hours=2)
    summary = _run(reddit, tmp_path, later)
    assert (summary.deleted, summary.removed, summary.tracking) == (1, 1, 3)

    frame = load_snapshots(tmp_path).frame
    status = frame[frame["knowledge_time"] == later].set_index("post_id")["status"].to_dict()
    assert status == {"live": "live", "gone": "deleted", "mod": "removed"}

    # They keep being snapshotted at the next age.
    summary = _run(reddit, tmp_path, FRIDAY + pd.Timedelta(hours=5))
    assert summary.snapshots == 3 and summary.deleted == 1 and summary.removed == 1


def test_post_status_mapping() -> None:
    assert post_status({}) == "live"
    assert post_status({"removed_by_category": "deleted"}) == "deleted"
    assert post_status({"removed_by_category": "automod_filtered"}) == "removed"
    assert post_status({"author": "[deleted]"}) == "deleted"
    assert post_status({"selftext": "[removed]"}) == "removed"


def test_post_missing_from_the_api_is_counted_not_invented(
    reddit: FakeReddit, tmp_path: Path
) -> None:
    reddit.add("a1", FRIDAY)
    _run(reddit, tmp_path, FRIDAY)
    del reddit.posts["a1"]
    summary = _run(reddit, tmp_path, FRIDAY + pd.Timedelta(hours=2))
    assert (summary.snapshots, summary.missing) == (0, 1)
    assert "1 not returned" in summary.describe()


def test_discovery_does_not_rediscover_posts(reddit: FakeReddit, tmp_path: Path) -> None:
    for i in range(130):
        reddit.add(f"p{i:03d}", FRIDAY + pd.Timedelta(seconds=i))
    # With no watermark yet, the first run reads a single page of 100.
    first = _run(reddit, tmp_path, FRIDAY + pd.Timedelta(minutes=10))
    assert first.discovered == 100
    for i in range(130, 150):
        reddit.add(f"p{i:03d}", FRIDAY + pd.Timedelta(seconds=i))
    second = _run(reddit, tmp_path, FRIDAY + pd.Timedelta(minutes=11))
    assert second.discovered == 20  # only the new ones, none twice


def test_info_requests_are_batched_at_100(reddit: FakeReddit, tmp_path: Path) -> None:
    for i in range(150):
        sub = "a" if i < 100 else "b"
        reddit.add(f"p{i:03d}", FRIDAY, subreddit=sub)
    summary = _run(reddit, tmp_path, FRIDAY, subs=("a", "b"))
    assert summary.discovered == 150
    _run(reddit, tmp_path, FRIDAY + pd.Timedelta(hours=2), subs=("a", "b"))
    assert reddit.info_batches == [100, 50]


def test_failed_run_leaves_state_untouched(reddit: FakeReddit, tmp_path: Path) -> None:
    reddit.add("a1", FRIDAY)
    _run(reddit, tmp_path, FRIDAY)
    before = (tmp_path / "state.json").read_text()

    def broken(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/info":
            return httpx.Response(400)
        return reddit(request)

    client = RedditClient("id", "s", "ua", transport=httpx.MockTransport(broken))
    with pytest.raises(httpx.HTTPStatusError):
        run_once(
            client,
            tmp_path / "state.json",
            tmp_path,
            ["stocks"],
            UNIVERSE,
            FRIDAY + pd.Timedelta(hours=2),
        )
    assert (tmp_path / "state.json").read_text() == before
    assert not list(tmp_path.rglob("*.tmp"))


def test_naive_now_is_rejected(reddit: FakeReddit, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        _run(reddit, tmp_path, pd.Timestamp("2024-01-12 20:00"))


# ------------------------------------------------------------ load_snapshots


def test_load_snapshots_feeds_engagement_scores(reddit: FakeReddit, tmp_path: Path) -> None:
    rng = np.random.default_rng(0)
    for i in range(6):
        reddit.add(f"p{i}", FRIDAY - pd.Timedelta(hours=i), title="$AAPL $NVDA")
    _run(reddit, tmp_path, FRIDAY + pd.Timedelta(minutes=5))
    for post in reddit.posts.values():
        post["score"] = int(rng.integers(5, 500))
    _run(reddit, tmp_path, FRIDAY + pd.Timedelta(days=2))

    store = load_snapshots(tmp_path)
    assert isinstance(store, PointInTimeStore)
    assert len(store) == 6 * 2 * 2  # posts x two tickers x two snapshots

    dates = pd.bdate_range("2024-01-08", periods=8)
    prices = pd.DataFrame(100.0, index=dates, columns=["AAPL", "NVDA"])
    data = MarketData(opens=prices, closes=prices, engagement=store)
    visible = engagement_scores(data, snapshot="visible")
    final = engagement_scores(data, snapshot="final")
    assert visible.shape == prices.shape
    assert visible.to_numpy().sum() > 0
    assert not visible.isna().any().any()
    assert final.to_numpy().sum() != visible.to_numpy().sum()


def test_load_snapshots_without_data_is_empty(tmp_path: Path) -> None:
    assert len(load_snapshots(tmp_path)) == 0


# --------------------------------------------------------------- credentials


def _settings(tmp_path: Path, **kwargs: Any) -> Settings:
    return Settings(_env_file=None, data_dir=tmp_path, **kwargs)  # type: ignore[call-arg]


def test_missing_credentials_skip_without_touching_anything(tmp_path: Path) -> None:
    def no_network(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request may be made without credentials")

    summary = collect_from_settings(
        _settings(tmp_path), UNIVERSE, transport=httpx.MockTransport(no_network)
    )
    assert summary.skipped and summary.reason == MISSING_CREDENTIALS
    assert summary.describe() == "skipped: SIGAUDIT_REDDIT_CLIENT_ID/SECRET not set"
    assert list(tmp_path.iterdir()) == []


def test_collect_from_settings_runs_with_credentials(reddit: FakeReddit, tmp_path: Path) -> None:
    reddit.add("a1", pd.Timestamp.now(tz="UTC") - pd.Timedelta(minutes=3))
    settings = _settings(
        tmp_path,
        reddit_client_id="id",
        reddit_client_secret=SecretStr("secret"),
        reddit_subreddits=["stocks"],
    )
    summary = collect_from_settings(settings, UNIVERSE, transport=httpx.MockTransport(reddit))
    assert not summary.skipped and summary.discovered == 1
    assert len(load_snapshots(tmp_path / "reddit")) == 1
    state = json.loads((tmp_path / "reddit" / "state.json").read_text())
    assert list(state["posts"]) == ["a1"]
