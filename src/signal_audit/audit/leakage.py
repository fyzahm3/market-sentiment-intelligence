"""Behavioural look-ahead detection.

The truncation test asks one question: if the future is removed from the
dataset, do the signal's past scores stay the same? For an honest signal they
must. If any past score changes, the signal was using information from after
the date it was scoring.

This treats the signal as a black box, so it finds leaks whether they sit in
the signal's code or in the timestamps of the data it reads. It cannot find a
model that memorised the future during training, or a ticker universe chosen
with hindsight.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from signal_audit.data.market import MarketData
from signal_audit.signals.base import Signal, align_scores


@dataclass(frozen=True)
class CutResult:
    cut: pd.Timestamp
    compared_cells: int
    mismatched_cells: int
    max_abs_diff: float
    first_mismatch: tuple[pd.Timestamp, str] | None

    @property
    def passed(self) -> bool:
        return self.mismatched_cells == 0


@dataclass(frozen=True)
class LeakReport:
    signal: str
    cuts: tuple[CutResult, ...]

    @property
    def passed(self) -> bool:
        return all(cut.passed for cut in self.cuts)

    @property
    def mismatched_cells(self) -> int:
        return sum(cut.mismatched_cells for cut in self.cuts)

    @property
    def first_mismatch(self) -> tuple[pd.Timestamp, str] | None:
        found = [cut.first_mismatch for cut in self.cuts if cut.first_mismatch is not None]
        return min(found, key=lambda item: item[0]) if found else None


def choose_cuts(dates: pd.DatetimeIndex, n_cuts: int, min_history: int) -> list[pd.Timestamp]:
    """Evenly spaced cut dates, leaving ``min_history`` sessions before the first."""
    last = len(dates) - 2  # leave at least one session of "future" to remove
    if last < min_history:
        raise ValueError(
            f"need more than {min_history + 1} sessions for the truncation test, got {len(dates)}"
        )
    positions = np.unique(np.linspace(min_history, last, n_cuts).round().astype(int))
    return [dates[int(p)] for p in positions]


def _compare(
    full: pd.DataFrame, truncated: pd.DataFrame, cut: pd.Timestamp, atol: float, rtol: float
) -> CutResult:
    a = full.to_numpy(dtype=float)
    b = truncated.to_numpy(dtype=float)
    a_nan, b_nan = np.isnan(a), np.isnan(b)

    with np.errstate(invalid="ignore"):
        diff = np.abs(a - b)
        differs = diff > (atol + rtol * np.abs(a))
    mismatch = (a_nan != b_nan) | (~a_nan & ~b_nan & differs)

    first: tuple[pd.Timestamp, str] | None = None
    if mismatch.any():
        row, col = np.argwhere(mismatch)[0]
        first = (pd.Timestamp(full.index[int(row)]), str(full.columns[int(col)]))

    finite = diff[~a_nan & ~b_nan]
    return CutResult(
        cut=cut,
        compared_cells=int(mismatch.size),
        mismatched_cells=int(mismatch.sum()),
        max_abs_diff=float(finite.max()) if finite.size else 0.0,
        first_mismatch=first,
    )


def truncation_test(
    signal: Signal,
    data: MarketData,
    n_cuts: int = 5,
    min_history: int = 90,
    atol: float = 1e-9,
    rtol: float = 1e-9,
) -> LeakReport:
    """Recompute the signal with the future removed and compare past scores."""
    full_scores = align_scores(signal.compute(data), data)

    results = []
    for cut in choose_cuts(data.dates, n_cuts, min_history):
        truncated_data = data.truncate(cut)
        truncated_scores = align_scores(signal.compute(truncated_data), truncated_data)
        results.append(_compare(full_scores.loc[:cut], truncated_scores, cut, atol, rtol))

    return LeakReport(signal=signal.name, cuts=tuple(results))
