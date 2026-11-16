"""Point-in-time storage.

Every record carries two timestamps:

* ``event_time``: when the thing happened (post created, article published).
* ``knowledge_time``: when this system could first have known about it.

"As of" queries filter on ``knowledge_time`` only. Filtering on ``event_time``
is the most common way look-ahead bias enters a text-based backtest.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = ("ticker", "event_time", "knowledge_time")
_TIME_COLUMNS = ("event_time", "knowledge_time")


def _require_utc(when: pd.Timestamp) -> pd.Timestamp:
    if when.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return when.tz_convert("UTC")


class PointInTimeStore:
    """An immutable table of records that can be queried 'as of' a moment."""

    def __init__(self, frame: pd.DataFrame) -> None:
        missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
        if missing:
            raise ValueError(f"missing required columns: {missing}")

        frame = frame.copy()
        for column in _TIME_COLUMNS:
            if not isinstance(frame[column].dtype, pd.DatetimeTZDtype):
                raise ValueError(f"{column} must be timezone-aware datetimes")
            frame[column] = frame[column].dt.tz_convert("UTC")

        if (frame["knowledge_time"] < frame["event_time"]).any():
            raise ValueError("knowledge_time cannot be earlier than event_time")

        self._frame = frame.sort_values("knowledge_time", kind="stable").reset_index(drop=True)

    @classmethod
    def empty(cls) -> PointInTimeStore:
        times = pd.Series([], dtype="datetime64[ns, UTC]")
        return cls(
            pd.DataFrame(
                {
                    "ticker": pd.Series([], dtype="object"),
                    "event_time": times,
                    "knowledge_time": times,
                }
            )
        )

    @classmethod
    def from_parquet(cls, path: Path) -> PointInTimeStore:
        return cls(pd.read_parquet(path))

    def to_parquet(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._frame.to_parquet(path, index=False)

    def __len__(self) -> int:
        return len(self._frame)

    @property
    def frame(self) -> pd.DataFrame:
        """A copy of every record, regardless of knowledge time."""
        return self._frame.copy()

    def as_of(self, when: pd.Timestamp) -> pd.DataFrame:
        """Records that were knowable at ``when``."""
        cutoff = _require_utc(when)
        return self._frame[self._frame["knowledge_time"] <= cutoff].copy()

    def truncate(self, when: pd.Timestamp) -> PointInTimeStore:
        """A new store containing only what was knowable at ``when``."""
        return PointInTimeStore(self.as_of(when))
