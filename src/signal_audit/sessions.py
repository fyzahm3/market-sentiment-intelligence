"""Trading-session times for US equities, from the NYSE calendar.

Sessions, holidays (with their weekend-observance rules), special closures such
as 2001-09-11 to 09-14 or 2025-01-09, and 13:00 early closes come from the
``XNYS`` calendar of the ``exchange_calendars`` package. The calendar covers
``CALENDAR_START`` to ``CALENDAR_END``; any date outside that range raises
``ValueError`` rather than being guessed.

``MarketData`` takes its sessions from its own price index. Real prices are
indexed by NYSE sessions. Synthetic data uses every weekday, so it can contain
dates that are NYSE holidays; ``session_open_utc`` and ``session_close_utc``
give such dates the regular 09:30 and 16:00 New York times.
"""

from __future__ import annotations

import datetime as dt
import warnings
from dataclasses import dataclass
from functools import lru_cache
from zoneinfo import ZoneInfo

import exchange_calendars as xcals
import numpy as np
import numpy.typing as npt
import pandas as pd

NEW_YORK = ZoneInfo("America/New_York")
OPEN_TIME = dt.time(9, 30)
CLOSE_TIME = dt.time(16, 0)
CALENDAR_START = dt.date(1990, 1, 1)
CALENDAR_END = dt.date(2099, 12, 31)


@dataclass(frozen=True)
class _Calendar:
    sessions: pd.DatetimeIndex  # tz-naive session dates
    opens_ns: npt.NDArray[np.int64]  # UTC nanoseconds, aligned with sessions
    closes_ns: npt.NDArray[np.int64]


@lru_cache(maxsize=1)
def _calendar() -> _Calendar:
    with warnings.catch_warnings():
        # exchange_calendars reads ``Series.values`` on tz-aware data, which pandas
        # 3.1 deprecates. The values it reads are UTC either way.
        warnings.filterwarnings(
            "ignore", message="Series.values returning an ndarray that drops timezone"
        )
        calendar = xcals.get_calendar(
            "XNYS", start=CALENDAR_START.isoformat(), end=CALENDAR_END.isoformat()
        )
    sessions = pd.DatetimeIndex(calendar.sessions).as_unit("ns")
    opens = pd.DatetimeIndex(calendar.opens.reindex(sessions)).tz_convert("UTC").as_unit("ns")
    closes = pd.DatetimeIndex(calendar.closes.reindex(sessions)).tz_convert("UTC").as_unit("ns")
    if opens.hasnans or closes.hasnans:
        raise RuntimeError("NYSE calendar has a session without an open or close time")
    return _Calendar(
        sessions=sessions,
        opens_ns=np.asarray(opens.asi8, dtype=np.int64),
        closes_ns=np.asarray(closes.asi8, dtype=np.int64),
    )


def _date(day: dt.date | pd.Timestamp) -> dt.date:
    date = pd.Timestamp(day).date()
    if not CALENDAR_START <= date <= CALENDAR_END:
        raise ValueError(
            f"{date} is outside the NYSE calendar range {CALENDAR_START} to {CALENDAR_END}"
        )
    return date


def _position(date: dt.date) -> int:
    """Index of ``date`` in the session list, or -1 if it is not a session."""
    sessions = _calendar().sessions
    pos = int(sessions.searchsorted(pd.Timestamp(date)))
    if pos < len(sessions) and sessions[pos].date() == date:
        return pos
    return -1


def _at(date: dt.date, when: dt.time) -> pd.Timestamp:
    local = dt.datetime.combine(date, when, tzinfo=NEW_YORK)
    return pd.Timestamp(local).tz_convert("UTC")


def is_session(day: dt.date | pd.Timestamp) -> bool:
    """True if the NYSE holds a session on ``day``."""
    return _position(_date(day)) >= 0


def is_early_close(day: dt.date | pd.Timestamp) -> bool:
    """True if ``day`` is a session that closes before 16:00 New York."""
    date = _date(day)
    return is_session(date) and session_close_utc(date) < _at(date, CLOSE_TIME)


def session_open_utc(day: dt.date | pd.Timestamp) -> pd.Timestamp:
    """The open of session ``day`` as a UTC timestamp (09:30 New York for a non-session)."""
    date = _date(day)
    pos = _position(date)
    if pos < 0:
        return _at(date, OPEN_TIME)
    return pd.Timestamp(int(_calendar().opens_ns[pos]), tz="UTC")


def session_close_utc(day: dt.date | pd.Timestamp) -> pd.Timestamp:
    """The close of session ``day`` as a UTC timestamp, early closes included.

    A date that is not an NYSE session gets the regular 16:00 New York close.
    """
    date = _date(day)
    pos = _position(date)
    if pos < 0:
        return _at(date, CLOSE_TIME)
    return pd.Timestamp(int(_calendar().closes_ns[pos]), tz="UTC")


def _vectorised(dates: pd.DatetimeIndex, regular: pd.Timedelta, column: str) -> pd.DatetimeIndex:
    days = pd.DatetimeIndex(dates).normalize().as_unit("ns")
    if len(days):
        _date(days.min())
        _date(days.max())
    local = (days + regular).tz_localize(NEW_YORK).tz_convert("UTC").as_unit("ns")
    values = np.asarray(local.asi8, dtype=np.int64).copy()
    calendar = _calendar()
    pos = calendar.sessions.get_indexer(days)
    known = pos >= 0
    values[known] = getattr(calendar, column)[pos[known]]
    return pd.DatetimeIndex(pd.to_datetime(values, utc=True))


def session_closes_utc(dates: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Vectorised ``session_close_utc`` for a tz-naive index of session dates."""
    return _vectorised(dates, pd.Timedelta(hours=16), "closes_ns")


def session_opens_utc(dates: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Vectorised ``session_open_utc`` for a tz-naive index of session dates."""
    return _vectorised(dates, pd.Timedelta(hours=9, minutes=30), "opens_ns")


def next_session(day: dt.date | pd.Timestamp) -> dt.date:
    """The first session strictly after ``day``."""
    date = _date(day)
    sessions = _calendar().sessions
    pos = int(sessions.searchsorted(pd.Timestamp(date), side="right"))
    if pos >= len(sessions):
        raise ValueError(f"no NYSE session after {date} within the calendar range")
    return sessions[pos].date()


def previous_session(day: dt.date | pd.Timestamp) -> dt.date:
    """The last session strictly before ``day``."""
    date = _date(day)
    sessions = _calendar().sessions
    pos = int(sessions.searchsorted(pd.Timestamp(date), side="left")) - 1
    if pos < 0:
        raise ValueError(f"no NYSE session before {date} within the calendar range")
    return sessions[pos].date()


def sessions_between(
    start: dt.date | pd.Timestamp, end: dt.date | pd.Timestamp
) -> pd.DatetimeIndex:
    """NYSE sessions from ``start`` to ``end``, both inclusive, as tz-naive dates."""
    first, last = pd.Timestamp(_date(start)), pd.Timestamp(_date(end))
    sessions = _calendar().sessions
    return sessions[(sessions >= first) & (sessions <= last)]


def last_completed_session(now: dt.datetime) -> dt.date:
    """The latest session whose close is at or before ``now`` (timezone-aware)."""
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    stamp = pd.Timestamp(now).tz_convert("UTC")
    _date(stamp.tz_convert(NEW_YORK).date())
    calendar = _calendar()
    pos = int(np.searchsorted(calendar.closes_ns, stamp.as_unit("ns").value, side="right")) - 1
    if pos < 0:
        raise ValueError(f"no NYSE session closed by {now}")
    return calendar.sessions[pos].date()


def assign_sessions(times: pd.Series, dates: pd.DatetimeIndex) -> npt.NDArray[np.intp]:
    """Map each UTC timestamp to the first session whose close is at or after it.

    Returns positions into ``dates``. A value equal to ``len(dates)`` means the
    timestamp falls after the last session's close.
    """
    # Compare as integer nanoseconds so differing datetime resolutions can't matter.
    closes = session_closes_utc(dates).as_unit("ns").asi8
    stamps = pd.DatetimeIndex(times).tz_convert("UTC").as_unit("ns").asi8
    return np.asarray(np.searchsorted(closes, stamps, side="left"), dtype=np.intp)
