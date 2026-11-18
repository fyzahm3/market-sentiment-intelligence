from __future__ import annotations

import datetime as dt
import json
from collections.abc import Sequence
from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner

from signal_audit import __version__, cli
from signal_audit.audit.backtest import BacktestConfig, run_backtest
from signal_audit.cli import app
from signal_audit.data.adapters.prices import PriceSource, prices_sha256
from signal_audit.data.market import MarketData
from signal_audit.data.synthetic import DEFAULT_TICKERS, synthetic_market
from signal_audit.ledger import Ledger, OutcomeLog
from signal_audit.ledger.outcomes import holding_window
from signal_audit.sessions import session_close_utc
from signal_audit.signals.examples import MomentumSignal, honest_signals
from signal_audit.signals.planted import planted_leaks
from tests.conftest import session_prices

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_leak_suite_passes() -> None:
    result = runner.invoke(app, ["leak-suite"])
    assert result.exit_code == 0, result.output
    n_leaks, n_honest = len(planted_leaks()), len(honest_signals())
    assert f"Planted leaks caught: {n_leaks}/{n_leaks}" in result.output
    assert f"wrongly flagged: 0/{n_honest}" in result.output


def test_demo_writes_report_cards(tmp_path: Path) -> None:
    result = runner.invoke(app, ["demo", "--permutations", "20", "--out", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "mention_spike.md").exists()
    assert (tmp_path / "leak_future_return.json").exists()


def test_ledger_verify(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    Ledger(path).append(
        "momentum",
        dt.date(2024, 1, 8),
        {"AAA": 0.5},
        made_at=dt.datetime(2024, 1, 8, 22, 0, tzinfo=dt.UTC),
    )
    ok = runner.invoke(app, ["ledger", "verify", str(path)])
    assert ok.exit_code == 0
    assert "1 entries verified" in ok.output

    path.write_text(path.read_text(encoding="utf-8").replace("0.5", "0.9"), encoding="utf-8")
    broken = runner.invoke(app, ["ledger", "verify", str(path)])
    assert broken.exit_code == 1


def test_ledger_verify_missing_file(tmp_path: Path) -> None:
    result = runner.invoke(app, ["ledger", "verify", str(tmp_path / "none.jsonl")])
    assert result.exit_code == 1


class FakeLoader:
    """Stands in for ``load_prices_cached``: synthetic prices, no network."""

    def __init__(self, data: MarketData) -> None:
        self.data = data
        self.calls: list[tuple[list[str], str, str, bool]] = []

    def __call__(
        self,
        tickers: Sequence[str],
        start: str,
        end: str,
        cache_dir: Path,
        *,
        refresh: bool = False,
    ) -> tuple[MarketData, PriceSource]:
        self.calls.append((list(tickers), start, end, refresh))
        source = PriceSource(
            provider="fake",
            provider_version="0.0",
            adjusted=True,
            downloaded_at=dt.datetime(2026, 11, 17, 12, 0, tzinfo=dt.UTC),
            sha256=prices_sha256(self.data),
            cache_file=cache_dir / "prices_fake.parquet",
        )
        return self.data, source


def _prices_only(n_days: int = 300) -> MarketData:
    market = synthetic_market(n_days=n_days, seed=5)
    return MarketData(opens=market.opens, closes=market.closes)


@pytest.fixture
def universe_file(tmp_path: Path) -> Path:
    path = tmp_path / "test_universe.txt"
    path.write_text("# synthetic\n" + "\n".join(DEFAULT_TICKERS) + "\n", encoding="utf-8")
    return path


def _audit_args(universe: Path, *extra: str) -> list[str]:
    return [
        "audit",
        "--universe",
        str(universe),
        "--start",
        "2021-01-01",
        "--end",
        "2022-01-01",
        "--permutations",
        "20",
        *extra,
    ]


def test_audit_writes_report_card(
    tmp_path: Path, universe_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    loader = FakeLoader(_prices_only())
    monkeypatch.setattr(cli, "load_prices_cached", loader)
    out = tmp_path / "reports"
    result = runner.invoke(
        app, _audit_args(universe_file, "--signal", "momentum", "--out", str(out), "--refresh")
    )
    assert result.exit_code == 0, result.output
    assert loader.calls == [(list(DEFAULT_TICKERS), "2021-01-01", "2022-01-01", True)]

    md = out / "momentum_test_universe.md"
    js = out / "momentum_test_universe.json"
    assert md.exists() and js.exists()
    markdown = md.read_text(encoding="utf-8")
    assert "## Data" in markdown
    assert "- Universe: test_universe: AAA, BBB" in markdown
    assert "- Source: fake 0.0, split/dividend adjusted" in markdown
    assert "- Non-positive prices: 0" in markdown
    assert "Market holidays" not in markdown
    assert "Data checks:" in result.output


def test_audit_rejects_unknown_signal(universe_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    loader = FakeLoader(_prices_only())
    monkeypatch.setattr(cli, "load_prices_cached", loader)
    for name in ("nonsense", "mention_spike"):
        result = runner.invoke(app, _audit_args(universe_file, "--signal", name))
        assert result.exit_code == 2, result.output
        assert "momentum, random" in result.output
    assert loader.calls == []


def test_audit_rejects_bad_dates(universe_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "load_prices_cached", FakeLoader(_prices_only()))
    args = _audit_args(universe_file, "--signal", "momentum")
    args[args.index("2022-01-01")] = "2020-01-01"
    assert runner.invoke(app, args).exit_code == 2


def test_audit_stops_on_sanity_failure(
    tmp_path: Path, universe_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = _prices_only()
    closes = data.closes.copy()
    closes.iloc[100, 2] = -1.0
    monkeypatch.setattr(
        cli, "load_prices_cached", FakeLoader(MarketData(opens=data.opens, closes=closes))
    )
    out = tmp_path / "reports"
    result = runner.invoke(
        app, _audit_args(universe_file, "--signal", "momentum", "--out", str(out))
    )
    assert result.exit_code == 1, result.output
    assert "sanity checks failed" in result.output
    assert "non_positive" in result.output
    assert not out.exists()


# --- ledger record / score / verify ---------------------------------------------------------

UTC = dt.UTC
# Tuesday 2024-12-31 16:30 New York: that session has closed, the next opens 2025-01-02.
AFTER_CLOSE = dt.datetime(2024, 12, 31, 21, 30, tzinfo=UTC)


class WindowLoader(FakeLoader):
    """Like ``FakeLoader`` but returns only the requested ``[start, end)`` window."""

    def __call__(
        self,
        tickers: Sequence[str],
        start: str,
        end: str,
        cache_dir: Path,
        *,
        refresh: bool = False,
    ) -> tuple[MarketData, PriceSource]:
        full, source = super().__call__(tickers, start, end, cache_dir, refresh=refresh)
        keep = (full.dates >= pd.Timestamp(start)) & (full.dates < pd.Timestamp(end))
        window = MarketData(
            opens=full.opens.loc[keep, list(tickers)], closes=full.closes.loc[keep, list(tickers)]
        )
        return window, source


def _clock(monkeypatch: pytest.MonkeyPatch, *times: dt.datetime) -> None:
    """Make ``cli._now`` return ``times`` in turn, then keep returning the last one."""
    queue = list(times)

    def now() -> dt.datetime:
        return queue.pop(0) if len(queue) > 1 else queue[0]

    monkeypatch.setattr(cli, "_now", now)


def _record(universe: Path, ledger: Path, signal: str = "momentum") -> list[str]:
    return [
        "ledger",
        "record",
        "--signal",
        signal,
        "--universe",
        str(universe),
        "--ledger",
        str(ledger),
    ]


def test_ledger_record_appends_latest_session(
    tmp_path: Path, universe_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = session_prices(dt.date(2024, 12, 31))
    loader = WindowLoader(data)
    monkeypatch.setattr(cli, "load_prices_cached", loader)
    _clock(monkeypatch, AFTER_CLOSE)
    ledger = tmp_path / "records" / "ledger.jsonl"

    result = runner.invoke(app, _record(universe_file, ledger))
    assert result.exit_code == 0, result.output
    assert "Recorded" in result.output
    assert loader.calls == [(sorted(DEFAULT_TICKERS), "2024-10-02", "2025-01-01", True)]

    (entry,) = Ledger(ledger).entries()
    assert (entry.signal, entry.universe, entry.top_k) == ("momentum", "test_universe", 3)
    assert entry.as_of == dt.date(2024, 12, 31)
    assert entry.made_at == AFTER_CLOSE
    expected = MomentumSignal().compute(data).iloc[-1]
    assert entry.scores == pytest.approx({str(t): float(v) for t, v in expected.items()})

    # Same session again: nothing appended, nothing downloaded.
    again = runner.invoke(app, _record(universe_file, ledger))
    assert again.exit_code == 0, again.output
    assert "Already recorded" in again.output
    assert len(Ledger(ledger).entries()) == 1
    assert len(loader.calls) == 1

    # A different signal on the same session is its own entry.
    other = runner.invoke(app, _record(universe_file, ledger, signal="random"))
    assert other.exit_code == 0, other.output
    assert [e.signal for e in Ledger(ledger).entries()] == ["momentum", "random"]


def test_ledger_record_on_a_holiday_after_recording(
    tmp_path: Path, universe_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    loader = WindowLoader(session_prices(dt.date(2024, 12, 31)))
    monkeypatch.setattr(cli, "load_prices_cached", loader)
    ledger = tmp_path / "ledger.jsonl"
    _clock(monkeypatch, AFTER_CLOSE)
    assert runner.invoke(app, _record(universe_file, ledger)).exit_code == 0

    # New Year's Day: no session, and 12-31 is already recorded.
    _clock(monkeypatch, dt.datetime(2025, 1, 1, 21, 30, tzinfo=UTC))
    result = runner.invoke(app, _record(universe_file, ledger))
    assert result.exit_code == 0, result.output
    assert "2025-01-01 is not an NYSE session" in result.output
    assert "Already recorded" in result.output
    assert len(Ledger(ledger).entries()) == 1
    assert len(loader.calls) == 1


def test_ledger_record_skips_when_latest_bar_is_missing(
    tmp_path: Path, universe_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The provider has not published 12-31 yet.
    monkeypatch.setattr(
        cli, "load_prices_cached", WindowLoader(session_prices(dt.date(2024, 12, 30)))
    )
    _clock(monkeypatch, AFTER_CLOSE)
    ledger = tmp_path / "ledger.jsonl"
    result = runner.invoke(app, _record(universe_file, ledger))
    assert result.exit_code == 0, result.output
    assert "not available yet" in result.output
    assert Ledger(ledger).entries() == []


def test_ledger_record_too_late(
    tmp_path: Path, universe_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    loader = WindowLoader(session_prices(dt.date(2024, 12, 31)))
    monkeypatch.setattr(cli, "load_prices_cached", loader)
    ledger = tmp_path / "ledger.jsonl"

    # During the 2025-01-02 session: 12-31 is the last completed session, but its
    # prediction window closed at the 01-02 open.
    _clock(monkeypatch, dt.datetime(2025, 1, 2, 15, 0, tzinfo=UTC))
    result = runner.invoke(app, _record(universe_file, ledger))
    assert result.exit_code == 1
    assert "Too late" in result.output
    assert loader.calls == []

    # Started in time, but the entry would be written after the deadline: the
    # ledger itself refuses it.
    _clock(monkeypatch, AFTER_CLOSE, dt.datetime(2025, 1, 2, 14, 30, tzinfo=UTC))
    late = runner.invoke(app, _record(universe_file, ledger))
    assert late.exit_code == 1
    assert "Not recorded" in late.output and "too late" in late.output
    assert Ledger(ledger).entries() == []


def test_ledger_record_rejects_bad_input(
    tmp_path: Path, universe_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    loader = WindowLoader(session_prices(dt.date(2024, 12, 31)))
    monkeypatch.setattr(cli, "load_prices_cached", loader)
    _clock(monkeypatch, AFTER_CLOSE)
    ledger = tmp_path / "ledger.jsonl"
    assert runner.invoke(app, _record(universe_file, ledger, signal="mention_spike")).exit_code == 2
    ledger.write_text("not json\n", encoding="utf-8")
    assert runner.invoke(app, _record(universe_file, ledger)).exit_code == 1
    assert loader.calls == []


def _record_days(
    days: list[dt.date], universe: Path, ledger: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for day in days:
        monkeypatch.setattr(
            cli, "load_prices_cached", WindowLoader(session_prices(dt.date(2024, 12, 31)))
        )
        _clock(monkeypatch, (session_close_utc(day) + pd.Timedelta(minutes=30)).to_pydatetime())
        result = runner.invoke(app, _record(universe, ledger))
        assert result.exit_code == 0, result.output
        assert "Recorded" in result.output


def _score(ledger: Path, outcomes: Path) -> list[str]:
    return ["ledger", "score", "--ledger", str(ledger), "--outcomes", str(outcomes)]


def test_ledger_score_appends_outcomes_once(
    tmp_path: Path, universe_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger, outcomes = tmp_path / "ledger.jsonl", tmp_path / "outcomes.jsonl"
    days = [dt.date(2024, 12, d) for d in (20, 23, 24, 26)]
    _record_days(days, universe_file, ledger, monkeypatch)

    data = session_prices(dt.date(2024, 12, 31))
    loader = WindowLoader(data)
    monkeypatch.setattr(cli, "load_prices_cached", loader)
    # Friday 12-27 after the close: entries up to 12-24 have exited (12-24 exits at the
    # 12-27 open); the 12-26 entry is still held.
    _clock(monkeypatch, dt.datetime(2024, 12, 27, 22, 0, tzinfo=UTC))
    result = runner.invoke(app, _score(ledger, outcomes))
    assert result.exit_code == 0, result.output
    assert "Scored 3 entries; 1 pending" in result.output
    assert loader.calls == [(sorted(DEFAULT_TICKERS), "2024-12-10", "2024-12-28", True)]

    records = OutcomeLog(outcomes).records()
    entries = Ledger(ledger).entries()
    assert [r.entry_seq for r in records] == [0, 1, 2]
    frame = pd.DataFrame(
        [e.scores for e in entries],
        index=pd.DatetimeIndex([pd.Timestamp(e.as_of) for e in entries]),
    )
    net = run_backtest(frame, data, BacktestConfig(top_k=3, cost_bps=10.0))
    gross = run_backtest(frame, data, BacktestConfig(top_k=3, cost_bps=0.0))
    for record in records:
        assert record.entered == holding_window(record.as_of)[0]
        assert record.net_return == pytest.approx(net.returns.loc[pd.Timestamp(record.entered)])
        assert record.gross_return == pytest.approx(gross.returns.loc[pd.Timestamp(record.entered)])

    # Nothing new has exited: no download, nothing appended.
    again = runner.invoke(app, _score(ledger, outcomes))
    assert again.exit_code == 0, again.output
    assert "Nothing to score" in again.output
    assert len(loader.calls) == 1

    # After the 12-30 open the last entry has exited too.
    _clock(monkeypatch, dt.datetime(2024, 12, 30, 22, 0, tzinfo=UTC))
    later = runner.invoke(app, _score(ledger, outcomes))
    assert later.exit_code == 0, later.output
    assert [r.entry_seq for r in OutcomeLog(outcomes).records()] == [0, 1, 2, 3]

    verified = runner.invoke(app, ["ledger", "verify", str(ledger), "--outcomes", str(outcomes)])
    assert verified.exit_code == 0, verified.output
    assert "4 entries verified" in verified.output
    assert "4 outcomes verified" in verified.output


def test_ledger_score_fails_loudly_on_a_price_gap(
    tmp_path: Path, universe_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger, outcomes = tmp_path / "ledger.jsonl", tmp_path / "outcomes.jsonl"
    _record_days([dt.date(2024, 12, 20)], universe_file, ledger, monkeypatch)
    data = session_prices(dt.date(2024, 12, 31))
    keep = data.dates != pd.Timestamp("2024-12-23")
    holed = MarketData(opens=data.opens[keep], closes=data.closes[keep])
    monkeypatch.setattr(cli, "load_prices_cached", WindowLoader(holed))
    _clock(monkeypatch, dt.datetime(2024, 12, 27, 22, 0, tzinfo=UTC))
    result = runner.invoke(app, _score(ledger, outcomes))
    assert result.exit_code == 1
    assert "could not be scored" in result.output
    assert "no bar for 2024-12-23" in result.output
    assert OutcomeLog(outcomes).records() == []


def test_ledger_score_without_a_ledger(tmp_path: Path) -> None:
    result = runner.invoke(app, _score(tmp_path / "none.jsonl", tmp_path / "o.jsonl"))
    assert result.exit_code == 0
    assert "nothing to score" in result.output


def test_ledger_verify_checks_outcomes(
    tmp_path: Path, universe_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger, outcomes = tmp_path / "ledger.jsonl", tmp_path / "outcomes.jsonl"
    _record_days([dt.date(2024, 12, 20)], universe_file, ledger, monkeypatch)
    verify = ["ledger", "verify", str(ledger), "--outcomes", str(outcomes)]
    missing = runner.invoke(app, verify)
    assert missing.exit_code == 1
    assert "No outcomes file" in missing.output

    monkeypatch.setattr(
        cli, "load_prices_cached", WindowLoader(session_prices(dt.date(2024, 12, 31)))
    )
    _clock(monkeypatch, dt.datetime(2024, 12, 27, 22, 0, tzinfo=UTC))
    assert runner.invoke(app, _score(ledger, outcomes)).exit_code == 0
    assert runner.invoke(app, verify).exit_code == 0

    unchecked = runner.invoke(app, ["ledger", "verify", str(ledger)])
    assert unchecked.exit_code == 0
    assert "Outcomes not checked" in unchecked.output

    text = outcomes.read_text(encoding="utf-8")
    record = json.loads(text)
    record["net_return"] = record["net_return"] + 0.01
    outcomes.write_text(json.dumps(record) + "\n", encoding="utf-8")
    tampered = runner.invoke(app, verify)
    assert tampered.exit_code == 1
    assert "Outcome verification failed" in tampered.output
    # Scoring refuses to extend a tampered outcomes file.
    assert runner.invoke(app, _score(ledger, outcomes)).exit_code == 1
