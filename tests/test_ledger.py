from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from signal_audit.ledger import Ledger, LedgerError
from signal_audit.ledger.ledger import GENESIS_HASH, prediction_deadline

UTC = dt.UTC
# Monday 2024-01-08. Its prediction window closes at Tuesday 09:30 New York (14:30 UTC).
AS_OF = dt.date(2024, 1, 8)
AFTER_CLOSE = dt.datetime(2024, 1, 8, 22, 0, tzinfo=UTC)


def _filled(path: Path) -> Ledger:
    ledger = Ledger(path)
    ledger.append("momentum", AS_OF, {"AAA": 0.5, "BBB": -0.1}, made_at=AFTER_CLOSE)
    ledger.append(
        "momentum",
        dt.date(2024, 1, 9),
        {"AAA": 0.2},
        made_at=dt.datetime(2024, 1, 9, 22, 0, tzinfo=UTC),
    )
    return ledger


def test_append_and_verify(tmp_path: Path) -> None:
    ledger = _filled(tmp_path / "ledger.jsonl")
    entries = ledger.entries()
    assert ledger.verify() == 2
    assert entries[0].prev_hash == GENESIS_HASH
    assert entries[1].prev_hash == entries[0].hash


def test_empty_ledger_verifies(tmp_path: Path) -> None:
    assert Ledger(tmp_path / "missing.jsonl").verify() == 0


def test_deadline_is_next_session_open() -> None:
    assert prediction_deadline(AS_OF) == dt.datetime(2024, 1, 9, 14, 30, tzinfo=UTC)
    # A Friday prediction stays open until Monday's open.
    assert prediction_deadline(dt.date(2024, 1, 12)) == dt.datetime(2024, 1, 15, 14, 30, tzinfo=UTC)


def test_rejects_late_prediction(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.jsonl")
    late = dt.datetime(2024, 1, 9, 14, 30, tzinfo=UTC)
    with pytest.raises(LedgerError, match="too late"):
        ledger.append("momentum", AS_OF, {"AAA": 0.5}, made_at=late)
    assert ledger.entries() == []


def test_rejects_out_of_order_entries(tmp_path: Path) -> None:
    ledger = _filled(tmp_path / "ledger.jsonl")
    with pytest.raises(LedgerError, match="earlier than the latest entry"):
        ledger.append("momentum", AS_OF, {"AAA": 0.1}, made_at=AFTER_CLOSE)


@pytest.mark.parametrize("scores", [{}, {"AAA": float("nan")}, {"AAA": float("inf")}])
def test_rejects_bad_scores(tmp_path: Path, scores: dict[str, float]) -> None:
    with pytest.raises(LedgerError):
        Ledger(tmp_path / "ledger.jsonl").append("momentum", AS_OF, scores, made_at=AFTER_CLOSE)


def test_rejects_naive_made_at(tmp_path: Path) -> None:
    with pytest.raises(LedgerError, match="timezone-aware"):
        Ledger(tmp_path / "ledger.jsonl").append(
            "momentum", AS_OF, {"AAA": 0.5}, made_at=dt.datetime(2024, 1, 8, 22, 0)
        )


def _rewrite(path: Path, line: int, **changes: object) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    record = json.loads(lines[line])
    record.update(changes)
    lines[line] = json.dumps(record)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_detects_edited_scores(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    ledger = _filled(path)
    _rewrite(path, 0, scores={"AAA": 0.9, "BBB": -0.1})
    with pytest.raises(LedgerError, match="do not match its hash"):
        ledger.verify()


def test_detects_removed_entry(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    ledger = _filled(path)
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text(lines[1] + "\n", encoding="utf-8")
    with pytest.raises(LedgerError):
        ledger.verify()


def test_detects_backdated_entry(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    ledger = _filled(path)
    _rewrite(path, 1, made_at="2024-01-08T23:00:00Z")
    with pytest.raises(LedgerError, match="do not match its hash"):
        ledger.verify()


def test_refuses_to_append_to_a_broken_ledger(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    ledger = _filled(path)
    _rewrite(path, 0, signal="something_else")
    with pytest.raises(LedgerError):
        ledger.append(
            "momentum",
            dt.date(2024, 1, 10),
            {"AAA": 0.3},
            made_at=dt.datetime(2024, 1, 10, 22, 0, tzinfo=UTC),
        )
