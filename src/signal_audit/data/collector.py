"""Forward collector of Reddit engagement snapshots.

A planned study measures how far archived engagement (score, comment count,
upvote ratio) differs from what was visible when a trading decision was made.
That can only be measured by collecting forward: every tracked post is
re-fetched at fixed ages and each fetch is stored as its own point-in-time
record (``event_time`` = post creation, ``knowledge_time`` = fetch time).

Only post ids, timestamps, numeric engagement and extracted tickers are kept.
Titles, bodies and author names are read once, at discovery, to tag tickers and
are then discarded. Nothing is written if a run fails part-way: the run raises
and the next run starts from the unchanged state.

If a run is late, a due post is fetched once at the actual fetch time, which is
what ``knowledge_time`` records. A tracked post the API no longer returns at
all is counted in ``RunSummary.missing`` and its schedule moves on; no row is
invented for it.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

import httpx
import pandas as pd

from signal_audit.config import Settings
from signal_audit.data.adapters.reddit import RedditClient, extract_tickers
from signal_audit.data.pit import PointInTimeStore
from signal_audit.sessions import NEW_YORK, is_session, next_session, session_close_utc

STATE_VERSION = 1
SNAPSHOT_DIR = "snapshots"
SNAPSHOT_COLUMNS = (
    "ticker",
    "event_time",
    "knowledge_time",
    "post_id",
    "subreddit",
    "score",
    "num_comments",
    "upvote_ratio",
    "status",
    "age_label",
    "age_hours",
    "run_id",
)
MISSING_CREDENTIALS = "skipped: SIGAUDIT_REDDIT_CLIENT_ID/SECRET not set"
_RECENT_IDS = 500

Status = Literal["live", "deleted", "removed"]


class RedditAPI(Protocol):
    """What the collector needs from a client (``RedditClient`` provides it)."""

    @property
    def api_calls(self) -> int: ...

    def fetch_new(
        self,
        subreddit: str,
        limit: int = 100,
        *,
        after: str | None = None,
        before: str | None = None,
    ) -> list[dict[str, Any]]: ...

    def fetch_info(self, fullnames: Sequence[str]) -> list[dict[str, Any]]: ...


# --------------------------------------------------------------------------
# Schedule (pure)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class SnapshotSchedule:
    """Ages at which a post is snapshotted.

    Targets: discovery (age 0), 1h, 4h, the close of the post's session, 36h
    and 7d, sorted by time. The session close can fall before the 1h or 4h
    targets for a post made in the afternoon.
    """

    fixed_hours: tuple[tuple[str, float], ...] = (
        ("1h", 1.0),
        ("4h", 4.0),
        ("36h", 36.0),
        ("7d", 168.0),
    )

    def targets(self, created: pd.Timestamp) -> list[tuple[str, pd.Timestamp]]:
        created = created.tz_convert("UTC")
        items = [("discovery", created), ("close", self.session_close(created))]
        items += [(label, created + pd.Timedelta(hours=hours)) for label, hours in self.fixed_hours]
        return sorted(items, key=lambda item: item[1])

    @staticmethod
    def session_close(created: pd.Timestamp) -> pd.Timestamp:
        """The first session close at or after ``created`` (16:00 New York)."""
        day = created.tz_convert(NEW_YORK).date()
        if not is_session(day) or created > session_close_utc(day):
            day = next_session(day)
        return session_close_utc(day)

    def size(self) -> int:
        return len(self.fixed_hours) + 2

    def advance(
        self, created: pd.Timestamp, next_index: int, now: pd.Timestamp
    ) -> tuple[int, str] | None:
        """Take one snapshot for every target that has passed by ``now``.

        Returns ``(new_next_index, label_of_latest_passed_target)``, or ``None``
        when nothing is due. Several passed targets collapse into one snapshot
        taken at the actual fetch time.
        """
        targets = self.targets(created)
        passed = [t for t in targets[next_index:] if t[1] <= now]
        if not passed:
            return None
        return next_index + len(passed), passed[-1][0]


# --------------------------------------------------------------------------
# State (JSON, atomic writes)
# --------------------------------------------------------------------------


@dataclass
class TrackedPost:
    subreddit: str
    created_utc: float
    tickers: list[str]
    next_index: int

    @property
    def created(self) -> pd.Timestamp:
        return pd.Timestamp(self.created_utc, unit="s", tz="UTC")


@dataclass
class CollectorState:
    posts: dict[str, TrackedPost] = field(default_factory=dict)
    watermarks: dict[str, float] = field(default_factory=dict)
    recent_ids: dict[str, list[str]] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> CollectorState:
        if not path.exists():
            return cls()
        raw = json.loads(path.read_text())
        if raw.get("version") != STATE_VERSION:
            raise ValueError(f"unsupported collector state version in {path}")
        return cls(
            posts={pid: TrackedPost(**data) for pid, data in raw["posts"].items()},
            watermarks={k: float(v) for k, v in raw["watermarks"].items()},
            recent_ids={k: list(v) for k, v in raw["recent_ids"].items()},
        )

    def save(self, path: Path) -> None:
        body = {
            "version": STATE_VERSION,
            "posts": {pid: vars(post) for pid, post in self.posts.items()},
            "watermarks": self.watermarks,
            "recent_ids": self.recent_ids,
        }
        _atomic_write(path, lambda tmp: tmp.write_text(json.dumps(body, indent=1, sort_keys=True)))


def _atomic_write(path: Path, write: Callable[[Path], object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    write(tmp)
    os.replace(tmp, path)


# --------------------------------------------------------------------------
# Summary
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class RunSummary:
    skipped: bool = False
    reason: str = ""
    discovered: int = 0
    snapshots: int = 0
    deleted: int = 0
    removed: int = 0
    missing: int = 0
    completed: int = 0
    tracking: int = 0
    api_calls: int = 0
    run_id: str = ""

    def describe(self) -> str:
        if self.skipped:
            return self.reason
        return (
            f"run {self.run_id}: discovered {self.discovered} posts, took {self.snapshots} "
            f"snapshot rows ({self.deleted} deleted, {self.removed} removed, "
            f"{self.missing} not returned by the API), {self.completed} posts finished, "
            f"{self.tracking} still tracked, {self.api_calls} API calls"
        )


# --------------------------------------------------------------------------
# Row building (pure)
# --------------------------------------------------------------------------


def post_status(post: Mapping[str, Any]) -> Status:
    """Whether the API reports the post as live, deleted by its author, or removed."""
    category = post.get("removed_by_category")
    if category == "deleted":
        return "deleted"
    if category:
        return "removed"
    if post.get("author") == "[deleted]" or post.get("selftext") == "[deleted]":
        return "deleted"
    if post.get("selftext") == "[removed]":
        return "removed"
    return "live"


def _rows(
    post_id: str,
    tracked: TrackedPost,
    data: Mapping[str, Any],
    fetched_at: pd.Timestamp,
    label: str,
    run_id: str,
) -> list[dict[str, Any]]:
    created = tracked.created
    known = max(fetched_at, created)
    ratio = data.get("upvote_ratio")
    return [
        {
            "ticker": ticker,
            "event_time": created,
            "knowledge_time": known,
            "post_id": post_id,
            "subreddit": tracked.subreddit,
            "score": int(data.get("score", 0)),
            "num_comments": int(data.get("num_comments", 0)),
            "upvote_ratio": float(ratio) if ratio is not None else float("nan"),
            "status": post_status(data),
            "age_label": label,
            "age_hours": (known - created).total_seconds() / 3600.0,
            "run_id": run_id,
        }
        for ticker in tracked.tickers
    ]


def _frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows, columns=list(SNAPSHOT_COLUMNS))
    for column in ("event_time", "knowledge_time"):
        frame[column] = pd.to_datetime(frame[column], utc=True)
    return frame.astype({"score": "int64", "num_comments": "int64", "upvote_ratio": "float64"})


# --------------------------------------------------------------------------
# One collection run
# --------------------------------------------------------------------------


def _run_id(now: pd.Timestamp) -> str:
    return now.tz_convert("UTC").strftime("%Y%m%dT%H%M%SZ")


def _discover(
    client: RedditAPI,
    state: CollectorState,
    subreddit: str,
    universe: set[str],
    now: Callable[[], pd.Timestamp],
    run_id: str,
    max_pages: int,
    rows: list[dict[str, Any]],
    schedule: SnapshotSchedule,
) -> int:
    watermark = state.watermarks.get(subreddit)
    seen = set(state.recent_ids.get(subreddit, []))
    new_ids: list[str] = []
    discovered = 0
    newest = watermark
    after: str | None = None
    # The first ever run only looks at one page: the history is not wanted.
    pages = max_pages if watermark is not None else 1
    for _ in range(pages):
        posts = client.fetch_new(subreddit, 100, after=after)
        fetched_at = now()
        if not posts:
            break
        reached_old = False
        for post in posts:
            post_id = str(post["id"])
            created_utc = float(post["created_utc"])
            if watermark is not None and created_utc < watermark:
                reached_old = True
                continue
            if post_id in seen or post_id in state.posts:
                continue
            new_ids.append(post_id)
            newest = created_utc if newest is None else max(newest, created_utc)
            text = f"{post.get('title', '')} {post.get('selftext', '')}"
            tickers = sorted(extract_tickers(text, universe))
            if not tickers:
                continue
            tracked = TrackedPost(subreddit, created_utc, tickers, 0)
            advanced = schedule.advance(tracked.created, 0, fetched_at)
            tracked.next_index = advanced[0] if advanced else 0
            rows.extend(_rows(post_id, tracked, post, fetched_at, "discovery", run_id))
            state.posts[post_id] = tracked
            discovered += 1
        if reached_old or len(posts) < 100:
            break
        after = f"t3_{posts[-1]['id']}"
    if newest is not None:
        state.watermarks[subreddit] = newest
    state.recent_ids[subreddit] = (new_ids + list(state.recent_ids.get(subreddit, [])))[
        :_RECENT_IDS
    ]
    return discovered


def run_once(
    client: RedditAPI,
    state_path: Path,
    out_dir: Path,
    subreddits: Iterable[str],
    universe: Iterable[str],
    now: pd.Timestamp,
    *,
    schedule: SnapshotSchedule | None = None,
    max_pages: int = 3,
    clock: Callable[[], pd.Timestamp] | None = None,
) -> RunSummary:
    """Discover new posts, snapshot them, and re-fetch every post that is due.

    ``now`` decides what is due. Rows are stamped with ``clock()`` as read after
    each response when a clock is given (use the real UTC time in production),
    otherwise with ``now``.
    """
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    now = now.tz_convert("UTC")
    schedule = schedule or SnapshotSchedule()
    stamp = clock if clock is not None else (lambda: now)
    allowed = set(universe)
    run_id = _run_id(now)
    calls_before = client.api_calls

    state = CollectorState.load(state_path)
    previously_tracked = list(state.posts)
    rows: list[dict[str, Any]] = []

    discovered = 0
    for subreddit in subreddits:
        discovered += _discover(
            client, state, subreddit, allowed, stamp, run_id, max_pages, rows, schedule
        )

    due: dict[str, tuple[int, str]] = {}
    for post_id in previously_tracked:
        tracked = state.posts[post_id]
        advanced = schedule.advance(tracked.created, tracked.next_index, now)
        if advanced is not None:
            due[post_id] = advanced

    missing = 0
    completed = 0
    ids = list(due)
    for start in range(0, len(ids), 100):
        batch = ids[start : start + 100]
        returned = {str(p["id"]): p for p in client.fetch_info(batch)}
        fetched_at = stamp()
        for post_id in batch:
            tracked = state.posts[post_id]
            new_index, label = due[post_id]
            data = returned.get(post_id)
            if data is None:
                missing += 1
            else:
                rows.extend(_rows(post_id, tracked, data, fetched_at, label, run_id))
            tracked.next_index = new_index
            if new_index >= schedule.size():
                del state.posts[post_id]
                completed += 1

    frame = _frame(rows)
    if len(frame):
        PointInTimeStore(frame)  # validates tz-aware UTC and knowledge_time >= event_time
        _write_partition(out_dir, now, run_id, frame)
    state.save(state_path)

    status = frame["status"] if len(frame) else pd.Series([], dtype="object")
    return RunSummary(
        discovered=discovered,
        snapshots=len(frame),
        deleted=int((status == "deleted").sum()),
        removed=int((status == "removed").sum()),
        missing=missing,
        completed=completed,
        tracking=len(state.posts),
        api_calls=client.api_calls - calls_before,
        run_id=run_id,
    )


def _write_partition(out_dir: Path, now: pd.Timestamp, run_id: str, frame: pd.DataFrame) -> Path:
    directory = out_dir / SNAPSHOT_DIR / f"date={now.date().isoformat()}"
    path = directory / f"part-{run_id}.parquet"
    suffix = 1
    while path.exists():
        path = directory / f"part-{run_id}-{suffix}.parquet"
        suffix += 1
    _atomic_write(path, lambda tmp: frame.to_parquet(tmp, index=False))
    return path


def load_snapshots(out_dir: Path) -> PointInTimeStore:
    """All stored snapshots as a store usable as ``MarketData.engagement``."""
    files = sorted((out_dir / SNAPSHOT_DIR).glob("date=*/part-*.parquet"))
    if not files:
        return PointInTimeStore.empty()
    return PointInTimeStore(pd.concat([pd.read_parquet(f) for f in files], ignore_index=True))


# --------------------------------------------------------------------------
# Settings entry point
# --------------------------------------------------------------------------


def collect_from_settings(
    settings: Settings,
    universe: Iterable[str],
    now: pd.Timestamp | None = None,
    *,
    transport: httpx.BaseTransport | None = None,
) -> RunSummary:
    """Run the collector with credentials from ``settings``.

    Without credentials this returns a skipped summary and touches nothing.
    """
    secret = settings.reddit_client_secret
    if not settings.reddit_client_id or secret is None or not secret.get_secret_value():
        return RunSummary(skipped=True, reason=MISSING_CREDENTIALS)
    client = RedditClient(
        settings.reddit_client_id,
        secret.get_secret_value(),
        settings.reddit_user_agent,
        transport=transport,
    )
    root = settings.data_dir / "reddit"
    try:
        return run_once(
            client,
            root / "state.json",
            root,
            settings.reddit_subreddits,
            universe,
            now if now is not None else pd.Timestamp.now(tz="UTC"),
            max_pages=settings.reddit_discovery_pages,
            clock=lambda: pd.Timestamp.now(tz="UTC"),
        )
    finally:
        client.close()


__all__ = [
    "MISSING_CREDENTIALS",
    "CollectorState",
    "RunSummary",
    "SnapshotSchedule",
    "TrackedPost",
    "collect_from_settings",
    "load_snapshots",
    "post_status",
    "run_once",
]
