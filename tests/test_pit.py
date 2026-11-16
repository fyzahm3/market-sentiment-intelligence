from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from signal_audit.data.pit import PointInTimeStore


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ticker": ["AAA", "BBB", "AAA"],
            "event_time": pd.to_datetime(
                ["2024-01-02 15:00", "2024-01-02 16:00", "2024-01-03 15:00"], utc=True
            ),
            "knowledge_time": pd.to_datetime(
                ["2024-01-02 15:05", "2024-01-04 09:00", "2024-01-03 15:01"], utc=True
            ),
        }
    )


def test_as_of_uses_knowledge_time_not_event_time() -> None:
    store = PointInTimeStore(_frame())
    seen = store.as_of(pd.Timestamp("2024-01-03 00:00", tz="UTC"))
    # The BBB record happened on the 2nd but was not known until the 4th.
    assert seen["ticker"].tolist() == ["AAA"]


def test_truncate_returns_a_smaller_store() -> None:
    store = PointInTimeStore(_frame())
    truncated = store.truncate(pd.Timestamp("2024-01-03 20:00", tz="UTC"))
    assert len(store) == 3
    assert len(truncated) == 2


def test_rejects_knowledge_before_event() -> None:
    frame = _frame()
    frame.loc[0, "knowledge_time"] = pd.Timestamp("2024-01-01", tz="UTC")
    with pytest.raises(ValueError, match="earlier than event_time"):
        PointInTimeStore(frame)


def test_rejects_naive_timestamps() -> None:
    frame = _frame()
    frame["event_time"] = frame["event_time"].dt.tz_localize(None)
    with pytest.raises(ValueError, match="timezone-aware"):
        PointInTimeStore(frame)


def test_rejects_missing_columns() -> None:
    with pytest.raises(ValueError, match="missing required columns"):
        PointInTimeStore(_frame().drop(columns=["knowledge_time"]))


def test_as_of_requires_aware_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        PointInTimeStore(_frame()).as_of(pd.Timestamp("2024-01-03"))


def test_parquet_round_trip(tmp_path: Path) -> None:
    store = PointInTimeStore(_frame())
    path = tmp_path / "docs.parquet"
    store.to_parquet(path)
    assert len(PointInTimeStore.from_parquet(path)) == len(store)


def test_empty_store() -> None:
    assert len(PointInTimeStore.empty()) == 0
