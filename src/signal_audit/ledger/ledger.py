"""Append-only, hash-chained record of predictions.

Each entry stores the hash of the one before it, so editing or removing any
past entry breaks every hash after it. Committing the file to a public git
repository adds an independent timestamp for each entry.

An entry is accepted only if it is made before the open of the session that
follows ``as_of``. After that point the outcome has started to be known and
the entry would no longer be a prediction.

``universe`` and ``top_k`` were added after the first format. They are part of
the hashed content only when set, so an entry written without them keeps the
hash it was written with.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
from pathlib import Path

from pydantic import BaseModel

from signal_audit.sessions import is_session, next_session, session_open_utc

GENESIS_HASH = "0" * 64


class LedgerError(Exception):
    """The ledger is corrupt, or an entry broke its rules."""


class LedgerEntry(BaseModel):
    seq: int
    made_at: dt.datetime
    signal: str
    as_of: dt.date
    scores: dict[str, float]
    prev_hash: str
    hash: str
    universe: str | None = None
    top_k: int | None = None


def _digest(
    seq: int,
    made_at: dt.datetime,
    signal: str,
    as_of: dt.date,
    scores: dict[str, float],
    prev_hash: str,
    universe: str | None = None,
    top_k: int | None = None,
) -> str:
    payload: dict[str, object] = {
        "seq": seq,
        "made_at": made_at.astimezone(dt.UTC).isoformat(),
        "signal": signal,
        "as_of": as_of.isoformat(),
        "scores": {ticker: repr(float(value)) for ticker, value in sorted(scores.items())},
        "prev_hash": prev_hash,
    }
    # Optional fields join the hashed content only when set, so entries written
    # before they existed keep their original hashes.
    if universe is not None:
        payload["universe"] = universe
    if top_k is not None:
        payload["top_k"] = top_k
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def prediction_deadline(as_of: dt.date) -> dt.datetime:
    """The latest moment a prediction for ``as_of`` still counts as a prediction."""
    return session_open_utc(next_session(as_of)).to_pydatetime()


class Ledger:
    def __init__(self, path: Path) -> None:
        self.path = path

    def entries(self) -> list[LedgerEntry]:
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8") as handle:
            return [LedgerEntry.model_validate_json(line) for line in handle if line.strip()]

    def find(self, signal: str, universe: str | None, as_of: dt.date) -> LedgerEntry | None:
        """The entry for ``signal`` on ``universe`` as of ``as_of``, if there is one."""
        for entry in self.entries():
            if (entry.signal, entry.universe, entry.as_of) == (signal, universe, as_of):
                return entry
        return None

    def verify(self) -> int:
        """Check the whole chain. Returns the number of entries, or raises."""
        prev_hash = GENESIS_HASH
        previous_made_at: dt.datetime | None = None
        entries = self.entries()
        for position, entry in enumerate(entries):
            if entry.seq != position:
                raise LedgerError(f"entry {position}: expected seq {position}, found {entry.seq}")
            if entry.prev_hash != prev_hash:
                raise LedgerError(f"entry {position}: does not link to the entry before it")
            expected = _digest(
                entry.seq,
                entry.made_at,
                entry.signal,
                entry.as_of,
                entry.scores,
                entry.prev_hash,
                entry.universe,
                entry.top_k,
            )
            if entry.hash != expected:
                raise LedgerError(f"entry {position}: contents do not match its hash")
            if entry.made_at >= prediction_deadline(entry.as_of):
                raise LedgerError(f"entry {position}: made after its prediction deadline")
            if previous_made_at is not None and entry.made_at < previous_made_at:
                raise LedgerError(f"entry {position}: made before the entry preceding it")
            prev_hash = entry.hash
            previous_made_at = entry.made_at
        return len(entries)

    def append(
        self,
        signal: str,
        as_of: dt.date,
        scores: dict[str, float],
        made_at: dt.datetime | None = None,
        *,
        universe: str | None = None,
        top_k: int | None = None,
    ) -> LedgerEntry:
        made_at = made_at or dt.datetime.now(dt.UTC)
        if made_at.tzinfo is None:
            raise LedgerError("made_at must be timezone-aware")
        if not is_session(as_of):
            raise LedgerError(f"{as_of} is not an NYSE session")
        if top_k is not None and top_k < 1:
            raise LedgerError("top_k must be at least 1")
        if universe is not None and not universe.strip():
            raise LedgerError("universe must not be blank")
        if not scores:
            raise LedgerError("an entry needs at least one score")
        if any(math.isnan(value) or math.isinf(value) for value in scores.values()):
            raise LedgerError("scores must be finite numbers")
        if made_at >= prediction_deadline(as_of):
            raise LedgerError(
                f"too late: predictions for {as_of} closed at {prediction_deadline(as_of)}"
            )

        self.verify()
        existing = self.entries()
        if existing and made_at < existing[-1].made_at:
            raise LedgerError("made_at is earlier than the latest entry")

        prev_hash = existing[-1].hash if existing else GENESIS_HASH
        seq = len(existing)
        clean = {ticker: float(value) for ticker, value in scores.items()}
        entry = LedgerEntry(
            seq=seq,
            made_at=made_at,
            signal=signal,
            as_of=as_of,
            scores=clean,
            prev_hash=prev_hash,
            hash=_digest(seq, made_at, signal, as_of, clean, prev_hash, universe, top_k),
            universe=universe,
            top_k=top_k,
        )

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(entry.model_dump_json() + "\n")
        return entry
