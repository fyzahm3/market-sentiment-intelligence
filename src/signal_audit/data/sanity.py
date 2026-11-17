"""Sanity checks on daily prices, run before auditing a signal on real data.

Pure functions: they take a ``MarketData`` and return a report. The checks look
for problems that would silently distort a backtest: non-positive prices,
holes in a ticker's history, gaps in the trading calendar, and overnight
moves that look like an unadjusted stock split.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from signal_audit.data.market import MarketData

KINDS = ("non_positive", "missing", "calendar_gap", "split_suspect")
FAILING_KINDS = ("non_positive", "split_suspect")
_BASE_SPLIT_FACTORS = (2.0, 3.0, 4.0, 5.0, 10.0, 1.5, 4.0 / 3.0)
SPLIT_FACTORS = tuple(sorted({*_BASE_SPLIT_FACTORS, *(1.0 / f for f in _BASE_SPLIT_FACTORS)}))


@dataclass(frozen=True)
class PriceIssue:
    kind: str
    ticker: str | None
    date: pd.Timestamp
    detail: str


@dataclass(frozen=True)
class SanityReport:
    n_sessions: int
    n_tickers: int
    issues: tuple[PriceIssue, ...]
    max_gap_weekdays: int = 4

    @property
    def passed(self) -> bool:
        return not any(i.kind in FAILING_KINDS for i in self.issues)

    def count(self, kind: str) -> int:
        return sum(1 for i in self.issues if i.kind == kind)

    def _first(self, kind: str) -> PriceIssue | None:
        return next((i for i in self.issues if i.kind == kind), None)

    def to_lines(self) -> list[str]:
        """One markdown bullet text per check, zero counts included."""
        lines = [f"Sessions: {self.n_sessions}, tickers: {self.n_tickers}"]

        lines.append(f"Non-positive prices: {self.count('non_positive')}")

        n_missing = self.count("missing")
        text = f"Missing ticker-days: {n_missing}"
        first_missing = self._first("missing")
        if first_missing is not None:
            text += f" (first: {first_missing.date:%Y-%m-%d} {first_missing.ticker})"
        lines.append(text)

        n_gaps = self.count("calendar_gap")
        text = f"Calendar gaps longer than {self.max_gap_weekdays} weekdays: {n_gaps}"
        first_gap = self._first("calendar_gap")
        if first_gap is not None:
            text += f" ({first_gap.detail})"
        lines.append(text)

        n_split = self.count("split_suspect")
        text = f"Split suspects: {n_split}"
        first_split = self._first("split_suspect")
        if first_split is None:
            text += " (adjusted prices; no overnight move near a split ratio)"
        else:
            text += f" (first: {first_split.date:%Y-%m-%d} {first_split.ticker}, "
            text += f"{first_split.detail})"
        lines.append(text)
        return lines


def check_prices(
    data: MarketData,
    *,
    max_gap_weekdays: int = 4,
    split_move: float = 0.30,
    split_ratio_tolerance: float = 0.05,
) -> SanityReport:
    """Run all price sanity checks and collect the issues found."""
    issues: list[PriceIssue] = []
    issues.extend(_non_positive(data))
    issues.extend(_missing(data))
    issues.extend(_calendar_gaps(data.dates, max_gap_weekdays))
    issues.extend(_split_suspects(data, split_move, split_ratio_tolerance))
    return SanityReport(
        n_sessions=len(data.dates),
        n_tickers=len(data.tickers),
        issues=tuple(issues),
        max_gap_weekdays=max_gap_weekdays,
    )


def _non_positive(data: MarketData) -> list[PriceIssue]:
    opens = data.opens.to_numpy(dtype=float)
    closes = data.closes.to_numpy(dtype=float)
    # NaN <= 0 is False, so missing values are ignored.
    bad = (opens <= 0) | (closes <= 0)
    issues = []
    for i, j in zip(*np.nonzero(bad), strict=True):
        issues.append(
            PriceIssue(
                kind="non_positive",
                ticker=data.tickers[j],
                date=data.dates[i],
                detail=f"open={opens[i, j]:.4g}, close={closes[i, j]:.4g}",
            )
        )
    return issues


def _missing(data: MarketData) -> list[PriceIssue]:
    opens = data.opens.isna().to_numpy()
    closes = data.closes.isna().to_numpy()
    started = np.maximum.accumulate(~(opens & closes), axis=0)
    holes = (opens | closes) & started
    issues = []
    for i, j in zip(*np.nonzero(holes), strict=True):
        what = (
            "open and close"
            if opens[i, j] and closes[i, j]
            else ("open" if opens[i, j] else "close")
        )
        issues.append(
            PriceIssue(
                kind="missing",
                ticker=data.tickers[j],
                date=data.dates[i],
                detail=f"{what} missing after the first valid price",
            )
        )
    return issues


def _calendar_gaps(dates: pd.DatetimeIndex, max_gap_weekdays: int) -> list[PriceIssue]:
    if len(dates) < 2:
        return []
    days = dates.to_numpy().astype("datetime64[D]")
    first_missing = days[:-1] + np.timedelta64(1, "D")
    # Weekdays strictly between consecutive sessions.
    n_missing = np.busday_count(first_missing, days[1:])
    issues = []
    for pos in np.nonzero(n_missing > max_gap_weekdays)[0]:
        k = int(pos)
        day = pd.Timedelta(days=1)
        missing = pd.bdate_range(dates[k] + day, dates[k + 1] - day)
        start, end = missing[0], missing[-1]
        issues.append(
            PriceIssue(
                kind="calendar_gap",
                ticker=None,
                date=start,
                detail=(
                    f"{start:%Y-%m-%d} to {end:%Y-%m-%d}, {len(missing)} weekdays without a session"
                ),
            )
        )
    return issues


def _nearest_factor(ratio: float) -> float:
    factors = np.asarray(SPLIT_FACTORS)
    return float(factors[np.argmin(np.abs(np.log(factors) - np.log(ratio)))])


def _split_suspects(data: MarketData, split_move: float, tolerance: float) -> list[PriceIssue]:
    opens = data.opens.to_numpy(dtype=float)
    closes = data.closes.to_numpy(dtype=float)
    prev = np.vstack([np.full((1, closes.shape[1]), np.nan), closes[:-1]])
    valid_prev = prev > 0

    factors = np.asarray(SPLIT_FACTORS)
    candidates = (("overnight", opens), ("close-to-close", closes))
    flagged: dict[tuple[int, int], str] = {}
    for label, cur in candidates:
        with np.errstate(divide="ignore", invalid="ignore"):
            ratio = np.where(valid_prev & (cur > 0), cur / prev, np.nan)
            big = np.abs(ratio - 1.0) > split_move
            near = np.abs(ratio[..., None] / factors - 1.0) <= tolerance
        hit = big & near.any(axis=-1)
        for i, j in zip(*np.nonzero(hit), strict=True):
            if (i, j) not in flagged:
                flagged[(int(i), int(j))] = (
                    f"{label} ratio {ratio[i, j]:.3f}, nearest split factor "
                    f"{_nearest_factor(float(ratio[i, j])):.3f}"
                )
    return [
        PriceIssue(kind="split_suspect", ticker=data.tickers[j], date=data.dates[i], detail=d)
        for (i, j), d in sorted(flagged.items())
    ]
