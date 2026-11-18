from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from signal_audit.audit.backtest import BacktestConfig, run_backtest
from signal_audit.data.market import MarketData
from signal_audit.ledger import Ledger, LedgerError, OutcomeLog
from signal_audit.ledger.outcomes import (
    OUTCOME_COST_BPS,
    due_entries,
    holding_window,
    score_entries,
)
from signal_audit.sessions import session_close_utc
from signal_audit.signals.examples import MomentumSignal
from tests.conftest import session_prices

UTC = dt.UTC
LAST = dt.date(2024, 12, 31)
# Around Thanksgiving 2024 (Thursday 11-28 closed, Friday 11-29 closes at 13:00).
AS_OFS = [dt.date(2024, 11, d) for d in (25, 26, 27, 29)] + [dt.date(2024, 12, 2)]
LATER = dt.datetime(2025, 1, 2, 22, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def data() -> MarketData:
    return session_prices(LAST, n_days=80)


def _scores(data: MarketData, as_of: dt.date) -> dict[str, float]:
    row = MomentumSignal().compute(data).loc[pd.Timestamp(as_of)]
    return {str(t): float(v) for t, v in row.items()}


def _ledger(path: Path, data: MarketData) -> Ledger:
    ledger = Ledger(path)
    for as_of in AS_OFS:
        made_at = (session_close_utc(as_of) + pd.Timedelta(minutes=30)).to_pydatetime()
        ledger.append(
            "momentum", as_of, _scores(data, as_of), made_at=made_at, universe="u", top_k=3
        )
    # Another signal on the same days is scored on its own.
    ledger.append(
        "random",
        AS_OFS[-1],
        {t: float(i) for i, t in enumerate(data.tickers)},
        made_at=(session_close_utc(AS_OFS[-1]) + pd.Timedelta(hours=1)).to_pydatetime(),
        universe="u",
        top_k=2,
    )
    return ledger


def test_holding_window_skips_holidays() -> None:
    assert holding_window(dt.date(2024, 11, 26)) == (dt.date(2024, 11, 27), dt.date(2024, 11, 29))
    assert holding_window(dt.date(2024, 11, 27)) == (dt.date(2024, 11, 29), dt.date(2024, 12, 2))


def test_scores_match_the_backtest(tmp_path: Path, data: MarketData) -> None:
    entries = _ledger(tmp_path / "ledger.jsonl", data).entries()
    due = due_entries(entries, set(), LATER)
    assert due == [e.seq for e in entries]
    run = score_entries(entries, due, data, LATER)
    assert run.pending == [] and run.failed == []
    assert [s.entry.seq for s in run.scored] == due

    momentum = [e for e in entries if e.signal == "momentum"]
    frame = pd.DataFrame(
        [e.scores for e in momentum],
        index=pd.DatetimeIndex([pd.Timestamp(e.as_of) for e in momentum]),
    )
    direct = run_backtest(frame, data, BacktestConfig(top_k=3, cost_bps=OUTCOME_COST_BPS))
    gross = run_backtest(frame, data, BacktestConfig(top_k=3, cost_bps=0.0))
    for scored in run.scored[: len(momentum)]:
        entered, exited = holding_window(scored.entry.as_of)
        assert scored.period.entered.date() == entered
        assert scored.period.exited.date() == exited
        when = pd.Timestamp(entered)
        assert scored.period.net_return == pytest.approx(direct.returns.loc[when])
        assert scored.period.gross_return == pytest.approx(gross.returns.loc[when])
        assert len(scored.period.weights) == 3

    # The first entry starts from cash; later ones trade from the previous session's weights.
    assert run.scored[0].period.turnover == pytest.approx(1.0)
    random = run.scored[-1]
    assert random.top_k == 2 and random.period.turnover == pytest.approx(1.0)
    assert list(random.period.weights.index) == data.tickers[-2:]


def test_entries_wait_for_the_exit_open(tmp_path: Path, data: MarketData) -> None:
    entries = _ledger(tmp_path / "ledger.jsonl", data).entries()
    # Monday 2024-12-02 just before the open: the 11-27 entry exits at this open.
    before_open = dt.datetime(2024, 12, 2, 14, 29, tzinfo=UTC)
    due = due_entries(entries, set(), before_open)
    assert [entries[s].as_of for s in due] == [dt.date(2024, 11, 25), dt.date(2024, 11, 26)]
    assert due_entries(entries, {0}, before_open) == [1]


def test_entries_wait_for_the_exit_bar(tmp_path: Path, data: MarketData) -> None:
    entries = _ledger(tmp_path / "ledger.jsonl", data).entries()
    short = MarketData(opens=data.opens.loc[:"2024-11-29"], closes=data.closes.loc[:"2024-11-29"])
    run = score_entries(entries, [0, 1, 2], short, LATER)
    assert [s.entry.seq for s in run.scored] == [0, 1]
    assert [p.entry.seq for p in run.pending] == [2]
    assert "no price bar for 2024-12-02" in run.pending[0].reason


def test_missing_bar_fails(tmp_path: Path, data: MarketData) -> None:
    entries = _ledger(tmp_path / "ledger.jsonl", data).entries()
    gap = data.dates != pd.Timestamp("2024-11-26")
    holed = MarketData(opens=data.opens[gap], closes=data.closes[gap])
    run = score_entries(entries, [0], holed, LATER)
    assert run.scored == []
    assert "no bar for 2024-11-26" in run.failed[0].reason


def test_unknown_return_fails(tmp_path: Path, data: MarketData) -> None:
    entries = _ledger(tmp_path / "ledger.jsonl", data).entries()
    opens = data.opens.copy()
    opens.loc[pd.Timestamp("2024-11-27")] = np.nan
    run = score_entries(entries, [0], MarketData(opens=opens, closes=data.closes), LATER)
    assert run.scored == []
    assert "no open-to-open return" in run.failed[0].reason


def test_duplicate_entries_for_one_day_are_refused(tmp_path: Path, data: MarketData) -> None:
    ledger = Ledger(tmp_path / "ledger.jsonl")
    for minutes in (30, 40):
        made_at = (session_close_utc(AS_OFS[0]) + pd.Timedelta(minutes=minutes)).to_pydatetime()
        ledger.append("momentum", AS_OFS[0], {"AAA": 1.0}, made_at=made_at, universe="u")
    with pytest.raises(LedgerError, match="more than one entry"):
        score_entries(ledger.entries(), [0, 1], data, LATER)


def _scored_log(tmp_path: Path, data: MarketData) -> tuple[OutcomeLog, Ledger]:
    ledger = _ledger(tmp_path / "ledger.jsonl", data)
    entries = ledger.entries()
    run = score_entries(entries, due_entries(entries, set(), LATER), data, LATER)
    log = OutcomeLog(tmp_path / "outcomes.jsonl")
    for scored in run.scored:
        log.append(scored, "synthetic test prices", entries, made_at=LATER)
    return log, ledger


def test_outcomes_chain_and_reference_the_ledger(tmp_path: Path, data: MarketData) -> None:
    log, ledger = _scored_log(tmp_path, data)
    entries = ledger.entries()
    records = log.records()
    assert log.verify(entries) == len(entries)
    assert [r.entry_seq for r in records] == [e.seq for e in entries]
    assert [r.entry_hash for r in records] == [e.hash for e in entries]
    assert records[1].prev_hash == records[0].hash
    first = records[0]
    assert (first.entered, first.exited) == (dt.date(2024, 11, 26), dt.date(2024, 11, 27))
    assert first.cost_bps == OUTCOME_COST_BPS
    assert first.net_return == pytest.approx(first.gross_return - first.turnover * 10 / 10_000)
    assert first.price_source == "synthetic test prices"
    assert log.scored_seqs() == {e.seq for e in entries}


def test_an_entry_is_scored_once(tmp_path: Path, data: MarketData) -> None:
    log, ledger = _scored_log(tmp_path, data)
    entries = ledger.entries()
    run = score_entries(entries, [0], data, LATER)
    with pytest.raises(LedgerError, match="already scored"):
        log.append(run.scored[0], "again", entries, made_at=LATER)


def test_outcome_cannot_precede_the_exit_open(tmp_path: Path, data: MarketData) -> None:
    entries = _ledger(tmp_path / "ledger.jsonl", data).entries()
    run = score_entries(entries, [0], data, LATER)
    log = OutcomeLog(tmp_path / "outcomes.jsonl")
    early = dt.datetime(2024, 11, 27, 14, 0, tzinfo=UTC)  # before the 11-27 open
    with pytest.raises(LedgerError, match="has not ended"):
        log.append(run.scored[0], "x", entries, made_at=early)
    assert log.records() == []


def _rewrite(path: Path, line: int, **changes: object) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    record = json.loads(lines[line])
    record.update(changes)
    lines[line] = json.dumps(record)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.mark.parametrize(
    "changes",
    [
        {"net_return": 0.5},
        {"gross_return": 0.5},
        {"weights": {"AAA": 1.0}},
        {"exited": "2024-12-03"},
        {"made_at": "2025-01-03T22:00:00Z"},
    ],
)
def test_tampered_outcome_is_detected(
    tmp_path: Path, data: MarketData, changes: dict[str, object]
) -> None:
    log, ledger = _scored_log(tmp_path, data)
    _rewrite(log.path, 1, **changes)
    with pytest.raises(LedgerError, match="outcome 1"):
        log.verify(ledger.entries())


def test_removed_outcome_is_detected(tmp_path: Path, data: MarketData) -> None:
    log, ledger = _scored_log(tmp_path, data)
    lines = log.path.read_text(encoding="utf-8").splitlines()
    log.path.write_text("\n".join(lines[1:]) + "\n", encoding="utf-8")
    with pytest.raises(LedgerError):
        log.verify(ledger.entries())


def test_outcomes_must_match_the_ledger(tmp_path: Path, data: MarketData) -> None:
    log, _ = _scored_log(tmp_path, data)
    other = Ledger(tmp_path / "other.jsonl")
    made_at = (session_close_utc(AS_OFS[0]) + pd.Timedelta(minutes=30)).to_pydatetime()
    other.append("momentum", AS_OFS[0], {"AAA": 1.0}, made_at=made_at, universe="u", top_k=3)
    with pytest.raises(LedgerError, match="hash does not match"):
        log.verify(other.entries())
    with pytest.raises(LedgerError, match="not found"):
        log.verify([])
