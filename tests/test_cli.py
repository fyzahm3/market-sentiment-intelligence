from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from pathlib import Path

import pytest
from typer.testing import CliRunner

from signal_audit import __version__, cli
from signal_audit.cli import app
from signal_audit.data.adapters.prices import PriceSource, prices_sha256
from signal_audit.data.market import MarketData
from signal_audit.data.synthetic import DEFAULT_TICKERS, synthetic_market
from signal_audit.ledger import Ledger
from signal_audit.signals.examples import honest_signals
from signal_audit.signals.planted import planted_leaks

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
