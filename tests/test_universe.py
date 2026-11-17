from __future__ import annotations

from pathlib import Path

import pytest

from signal_audit.data.universe import load_universe, parse_universe

REPO = Path(__file__).resolve().parents[1]


def test_parse_skips_comments_and_blanks_and_upper_cases() -> None:
    text = "# header\n\nxlk\n  XLF  # financials\nbrk.b\nBF-B\n"
    assert parse_universe(text) == ["XLK", "XLF", "BRK.B", "BF-B"]


def test_parse_deduplicates_preserving_order() -> None:
    assert parse_universe("XLK\nXLF\nxlk\nXLB\nXLF\n") == ["XLK", "XLF", "XLB"]


def test_empty_universe_raises() -> None:
    with pytest.raises(ValueError, match="empty"):
        parse_universe("# only a comment\n\n")


@pytest.mark.parametrize("bad", ["XL K", "XLK$", "X/Y", "ÄBC"])
def test_invalid_ticker_raises(bad: str) -> None:
    with pytest.raises(ValueError, match="invalid ticker"):
        parse_universe(f"XLK\n{bad}\n")


def test_load_universe_names_the_file(tmp_path: Path) -> None:
    path = tmp_path / "u.txt"
    path.write_text("\n", encoding="utf-8")
    with pytest.raises(ValueError, match=r"u\.txt: universe is empty"):
        load_universe(path)


def test_sector_etf_universe_file() -> None:
    tickers = load_universe(REPO / "universes" / "us_sector_etfs.txt")
    assert tickers == ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]
