"""Trading-session times for US equities.

v0 limitation: every weekday is treated as a session. Market holidays and early
closes are not handled yet (see docs/SPEC.md, milestone M3).
"""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

import numpy as np
import numpy.typing as npt
import pandas as pd

NEW_YORK = ZoneInfo("America/New_York")
OPEN_TIME = dt.time(9, 30)
CLOSE_TIME = dt.time(16, 0)


def _at(day: dt.date | pd.Timestamp, when: dt.time) -> pd.Timestamp:
    date = pd.Timestamp(day).date()
    local = dt.datetime.combine(date, when, tzinfo=NEW_YORK)
    return pd.Timestamp(local).tz_convert("UTC")


def session_open_utc(day: dt.date | pd.Timestamp) -> pd.Timestamp:
    """09:30 New York on ``day``, as a UTC timestamp."""
    return _at(day, OPEN_TIME)


def session_close_utc(day: dt.date | pd.Timestamp) -> pd.Timestamp:
    """16:00 New York on ``day``, as a UTC timestamp."""
    return _at(day, CLOSE_TIME)


def session_closes_utc(dates: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Vectorised ``session_close_utc`` for a tz-naive index of session dates."""
    local = (dates.normalize() + pd.Timedelta(hours=16)).tz_localize(NEW_YORK)
    return local.tz_convert("UTC")


def session_opens_utc(dates: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Vectorised ``session_open_utc`` for a tz-naive index of session dates."""
    local = (dates.normalize() + pd.Timedelta(hours=9, minutes=30)).tz_localize(NEW_YORK)
    return local.tz_convert("UTC")


def is_session(day: dt.date | pd.Timestamp) -> bool:
    return pd.Timestamp(day).weekday() < 5


def next_session(day: dt.date | pd.Timestamp) -> dt.date:
    """The first session strictly after ``day``."""
    current = pd.Timestamp(day).date() + dt.timedelta(days=1)
    while not is_session(current):
        current += dt.timedelta(days=1)
    return current


def assign_sessions(times: pd.Series, dates: pd.DatetimeIndex) -> npt.NDArray[np.intp]:
    """Map each UTC timestamp to the first session whose close is at or after it.

    Returns positions into ``dates``. A value equal to ``len(dates)`` means the
    timestamp falls after the last session's close.
    """
    # Compare as integer nanoseconds so differing datetime resolutions can't matter.
    closes = session_closes_utc(dates).as_unit("ns").asi8
    stamps = pd.DatetimeIndex(times).tz_convert("UTC").as_unit("ns").asi8
    return np.asarray(np.searchsorted(closes, stamps, side="left"), dtype=np.intp)
