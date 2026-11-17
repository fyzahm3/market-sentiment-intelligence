"""Ticker universe files: one ticker per line, ``#`` comments, blank lines ignored."""

from __future__ import annotations

import re
from pathlib import Path

_TICKER = re.compile(r"^[A-Z0-9.\-]+$")


def parse_universe(text: str) -> list[str]:
    """Parse universe file contents into upper-case tickers, de-duplicated in order."""
    tickers: list[str] = []
    seen: set[str] = set()
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        ticker = line.upper()
        if not _TICKER.fullmatch(ticker):
            raise ValueError(f"line {number}: invalid ticker {line!r}")
        if ticker not in seen:
            seen.add(ticker)
            tickers.append(ticker)
    if not tickers:
        raise ValueError("universe is empty")
    return tickers


def load_universe(path: Path) -> list[str]:
    """Read a universe file. Raises ``ValueError`` if it is empty or has an invalid ticker."""
    try:
        return parse_universe(Path(path).read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ValueError(f"{path}: {exc}") from exc
