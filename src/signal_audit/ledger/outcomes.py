"""Realised outcomes of ledger predictions, in their own hash-chained file.

Predictions are never edited. Once an entry's holding period is over (entered
at the open of the session after ``as_of``, exited at the open of the session
after that), one outcome record is appended here. Each record names the ledger
entry it scores by ``seq`` and ``hash`` and carries its own hash chain, so
neither file can be altered without ``verify`` noticing.

Returns come from ``signal_audit.audit.backtest``: the top-k long-only return
before costs and net of ``OUTCOME_COST_BPS`` on turnover. Turnover is measured
against the previous session's ledger weights for the same signal, universe
and top-k (cash if there was no entry that session), as in the backtest.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from pydantic import BaseModel

from signal_audit.audit.backtest import BacktestConfig, HoldingPeriod, holding_periods
from signal_audit.data.market import MarketData
from signal_audit.ledger.ledger import GENESIS_HASH, LedgerEntry, LedgerError
from signal_audit.sessions import next_session, previous_session, session_open_utc

OUTCOME_COST_BPS = 10.0
DEFAULT_TOP_K = BacktestConfig().top_k
"""Used for entries written before ``top_k`` was recorded; the outcome states it."""


class Outcome(BaseModel):
    seq: int
    made_at: dt.datetime
    entry_seq: int
    entry_hash: str
    signal: str
    universe: str | None
    as_of: dt.date
    top_k: int
    entered: dt.date  # bought at this session's open
    exited: dt.date  # sold at this session's open
    weights: dict[str, float]
    ticker_returns: dict[str, float]
    gross_return: float
    turnover: float
    cost_bps: float
    net_return: float
    price_source: str
    prev_hash: str
    hash: str


def _digest(fields: dict[str, object]) -> str:
    canonical = json.dumps(fields, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _hashed_content(outcome: Outcome) -> dict[str, object]:
    fields = outcome.model_dump(mode="json", exclude={"hash"})
    fields["made_at"] = outcome.made_at.astimezone(dt.UTC).isoformat()
    return fields


def holding_window(as_of: dt.date) -> tuple[dt.date, dt.date]:
    """(entry session, exit session) for a prediction made as of ``as_of``."""
    entered = next_session(as_of)
    return entered, next_session(entered)


@dataclass(frozen=True)
class Scored:
    entry: LedgerEntry
    top_k: int
    period: HoldingPeriod


@dataclass(frozen=True)
class Skipped:
    entry: LedgerEntry
    reason: str


@dataclass(frozen=True)
class ScoreRun:
    scored: list[Scored]
    pending: list[Skipped]  # holding period not over, or its exit bar not in the data yet
    failed: list[Skipped]  # holding period over, but the data cannot score it


def _group_key(entry: LedgerEntry) -> tuple[str, str | None, int]:
    return entry.signal, entry.universe, entry.top_k or DEFAULT_TOP_K


def due_entries(entries: list[LedgerEntry], scored_seqs: set[int], now: dt.datetime) -> list[int]:
    """Seqs of unscored entries whose exit session has opened by ``now``."""
    due = []
    for entry in entries:
        if entry.seq in scored_seqs:
            continue
        _, exited = holding_window(entry.as_of)
        if session_open_utc(exited) <= now:
            due.append(entry.seq)
    return due


def score_entries(
    entries: list[LedgerEntry], due: list[int], data: MarketData, now: dt.datetime
) -> ScoreRun:
    """Score the ledger entries whose seq is in ``due`` against ``data``.

    ``entries`` is the whole ledger: earlier entries of the same signal set the
    weights that turnover is measured from.
    """
    groups: dict[tuple[str, str | None, int], list[LedgerEntry]] = defaultdict(list)
    for entry in entries:
        groups[_group_key(entry)].append(entry)

    wanted = set(due)
    scored: list[Scored] = []
    pending: list[Skipped] = []
    failed: list[Skipped] = []
    dates = data.dates
    last = dates[-1].date() if len(dates) else None
    for (_, _, top_k), members in groups.items():
        targets = [e for e in members if e.seq in wanted]
        if not targets:
            continue
        as_ofs = [pd.Timestamp(e.as_of) for e in members]
        if len(set(as_ofs)) != len(as_ofs):
            raise LedgerError(
                f"ledger has more than one entry for {members[0].signal} on the same date"
            )
        scores = pd.DataFrame([e.scores for e in members], index=pd.DatetimeIndex(as_ofs))
        config = BacktestConfig(top_k=top_k, cost_bps=OUTCOME_COST_BPS)
        periods = holding_periods(scores.sort_index(), data, config)

        for entry in targets:
            entered, exited = holding_window(entry.as_of)
            if session_open_utc(exited) > now:
                pending.append(Skipped(entry, f"holding period ends at the open of {exited}"))
                continue
            if last is None or exited > last:
                pending.append(Skipped(entry, f"no price bar for {exited} yet"))
                continue
            needed = [previous_session(entry.as_of), entry.as_of, entered, exited]
            missing = [d for d in needed if pd.Timestamp(d) not in dates]
            if missing:
                listed = ", ".join(str(d) for d in missing)
                failed.append(Skipped(entry, f"price data has no bar for {listed}"))
                continue
            positions = [int(p) for p in dates.get_indexer(pd.DatetimeIndex(needed))]
            if positions != list(range(positions[0], positions[0] + len(needed))):
                failed.append(Skipped(entry, "price data has dates that are not NYSE sessions"))
                continue
            period = periods.get(pd.Timestamp(entry.as_of))
            if period is None:
                failed.append(Skipped(entry, "no holding period could be computed"))
                continue
            unknown = [str(t) for t, r in period.ticker_returns.items() if not math.isfinite(r)]
            if unknown:
                failed.append(Skipped(entry, f"no open-to-open return for {', '.join(unknown)}"))
                continue
            scored.append(Scored(entry, top_k, period))
    scored.sort(key=lambda s: s.entry.seq)
    return ScoreRun(scored=scored, pending=pending, failed=failed)


class OutcomeLog:
    def __init__(self, path: Path) -> None:
        self.path = path

    def records(self) -> list[Outcome]:
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8") as handle:
            return [Outcome.model_validate_json(line) for line in handle if line.strip()]

    def scored_seqs(self) -> set[int]:
        return {record.entry_seq for record in self.records()}

    def verify(self, entries: list[LedgerEntry]) -> int:
        """Check the chain and that every record scores a real ledger entry."""
        prev_hash = GENESIS_HASH
        previous_made_at: dt.datetime | None = None
        seen: set[int] = set()
        records = self.records()
        for position, record in enumerate(records):
            where = f"outcome {position}"
            if record.seq != position:
                raise LedgerError(f"{where}: expected seq {position}, found {record.seq}")
            if record.prev_hash != prev_hash:
                raise LedgerError(f"{where}: does not link to the outcome before it")
            if record.hash != _digest(_hashed_content(record)):
                raise LedgerError(f"{where}: contents do not match its hash")
            if not 0 <= record.entry_seq < len(entries):
                raise LedgerError(f"{where}: refers to ledger entry {record.entry_seq}, not found")
            entry = entries[record.entry_seq]
            if record.entry_hash != entry.hash:
                raise LedgerError(f"{where}: ledger entry {entry.seq} hash does not match")
            if (record.signal, record.universe, record.as_of) != (
                entry.signal,
                entry.universe,
                entry.as_of,
            ):
                raise LedgerError(f"{where}: does not describe ledger entry {entry.seq}")
            if record.entry_seq in seen:
                raise LedgerError(f"{where}: ledger entry {entry.seq} is scored twice")
            if (record.entered, record.exited) != holding_window(record.as_of):
                raise LedgerError(f"{where}: holding period does not follow from as_of")
            if record.made_at < session_open_utc(record.exited):
                raise LedgerError(f"{where}: made before its holding period ended")
            if previous_made_at is not None and record.made_at < previous_made_at:
                raise LedgerError(f"{where}: made before the outcome preceding it")
            seen.add(record.entry_seq)
            prev_hash = record.hash
            previous_made_at = record.made_at
        return len(records)

    def append(
        self,
        scored: Scored,
        price_source: str,
        entries: list[LedgerEntry],
        made_at: dt.datetime | None = None,
    ) -> Outcome:
        made_at = made_at or dt.datetime.now(dt.UTC)
        if made_at.tzinfo is None:
            raise LedgerError("made_at must be timezone-aware")
        self.verify(entries)
        existing = self.records()
        entry, period = scored.entry, scored.period
        if entry.seq in {r.entry_seq for r in existing}:
            raise LedgerError(f"ledger entry {entry.seq} is already scored")
        if existing and made_at < existing[-1].made_at:
            raise LedgerError("made_at is earlier than the latest outcome")

        fields: dict[str, object] = {
            "seq": len(existing),
            "made_at": made_at,
            "entry_seq": entry.seq,
            "entry_hash": entry.hash,
            "signal": entry.signal,
            "universe": entry.universe,
            "as_of": entry.as_of,
            "top_k": scored.top_k,
            "entered": period.entered.date(),
            "exited": period.exited.date(),
            "weights": {str(t): float(w) for t, w in period.weights.items()},
            "ticker_returns": {str(t): float(r) for t, r in period.ticker_returns.items()},
            "gross_return": period.gross_return,
            "turnover": period.turnover,
            "cost_bps": OUTCOME_COST_BPS,
            "net_return": period.net_return,
            "price_source": price_source,
            "prev_hash": existing[-1].hash if existing else GENESIS_HASH,
            "hash": "",
        }
        draft = Outcome.model_validate(fields)
        try:
            digest = _digest(_hashed_content(draft))
        except ValueError as exc:
            raise LedgerError(f"outcome for entry {entry.seq} has a non-finite number") from exc
        outcome = draft.model_copy(update={"hash": digest})
        if (outcome.entered, outcome.exited) != holding_window(outcome.as_of):
            raise LedgerError(f"entry {entry.seq}: holding period does not follow from as_of")
        if made_at < session_open_utc(outcome.exited):
            raise LedgerError(f"entry {entry.seq}: holding period has not ended")

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(outcome.model_dump_json() + "\n")
        return outcome
