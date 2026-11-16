from __future__ import annotations

import datetime as dt
from pathlib import Path

from typer.testing import CliRunner

from signal_audit import __version__
from signal_audit.cli import app
from signal_audit.ledger import Ledger

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_leak_suite_passes() -> None:
    result = runner.invoke(app, ["leak-suite"])
    assert result.exit_code == 0, result.output
    assert "Planted leaks caught: 5/5" in result.output
    assert "wrongly flagged: 0/3" in result.output


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
