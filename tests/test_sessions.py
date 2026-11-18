from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from signal_audit.sessions import (
    CALENDAR_END,
    CALENDAR_START,
    assign_sessions,
    is_early_close,
    is_session,
    last_completed_session,
    next_session,
    previous_session,
    session_close_utc,
    session_closes_utc,
    session_open_utc,
    session_opens_utc,
    sessions_between,
)

UTC = dt.UTC

# Full-day NYSE holidays, including weekend-observance rules.
HOLIDAYS = [
    "2023-01-02",  # New Year's Day on a Sunday, observed Monday
    "2024-01-01",  # New Year's Day
    "2024-01-15",  # Martin Luther King Jr. Day
    "2024-02-19",  # Presidents' Day
    "2024-03-29",  # Good Friday
    "2024-05-27",  # Memorial Day
    "2022-06-20",  # Juneteenth on a Sunday, observed Monday (first year)
    "2024-06-19",  # Juneteenth
    "2020-07-03",  # Independence Day on a Saturday, observed Friday
    "2021-07-05",  # Independence Day on a Sunday, observed Monday
    "2024-07-04",  # Independence Day
    "2024-09-02",  # Labor Day
    "2024-11-28",  # Thanksgiving
    "2021-12-24",  # Christmas on a Saturday, observed Friday
    "2022-12-26",  # Christmas on a Sunday, observed Monday
    "2024-12-25",  # Christmas
    "2026-07-03",  # Independence Day on a Saturday, observed Friday
    "2026-11-26",  # Thanksgiving
]

SPECIAL_CLOSURES = [
    "2001-09-11",
    "2001-09-12",
    "2001-09-13",
    "2001-09-14",  # September 11 attacks
    "2004-06-11",  # Reagan national day of mourning
    "2007-01-02",  # Ford national day of mourning
    "2012-10-29",
    "2012-10-30",  # Hurricane Sandy
    "2018-12-05",  # George H. W. Bush national day of mourning
    "2025-01-09",  # Carter national day of mourning
]

SESSIONS = [
    "2021-12-31",  # New Year's Day 2022 fell on Saturday: NYSE does not observe it on Friday
    "2021-06-18",  # Juneteenth was not yet an NYSE holiday in 2021
    "2001-09-17",  # reopening after September 11
    "2024-11-29",  # day after Thanksgiving (early close)
    "2024-01-08",
]

# 13:00 New York closes.
EARLY_CLOSES = [
    "2019-07-03",  # day before Independence Day
    "2024-07-03",
    "2025-07-03",
    "2023-11-24",  # day after Thanksgiving
    "2024-11-29",
    "2026-11-27",
    "2024-12-24",  # Christmas Eve
    "2025-12-24",
]


@pytest.mark.parametrize("day", HOLIDAYS + SPECIAL_CLOSURES)
def test_holidays_and_special_closures_are_not_sessions(day: str) -> None:
    assert not is_session(dt.date.fromisoformat(day))


@pytest.mark.parametrize("day", SESSIONS)
def test_known_sessions(day: str) -> None:
    assert is_session(dt.date.fromisoformat(day))


def test_weekends_are_not_sessions() -> None:
    assert not is_session(dt.date(2024, 1, 6))
    assert not is_session(pd.Timestamp("2024-01-07"))


@pytest.mark.parametrize("day", EARLY_CLOSES)
def test_early_closes_at_one_pm(day: str) -> None:
    date = dt.date.fromisoformat(day)
    close = session_close_utc(date).tz_convert("America/New_York")
    assert (close.hour, close.minute) == (13, 0)
    assert is_early_close(date)


def test_no_early_close_when_independence_day_is_observed_on_a_monday() -> None:
    # 2022-07-04 was a Monday; the Friday before was a full session.
    assert not is_early_close(dt.date(2022, 7, 1))
    assert not is_early_close(dt.date(2024, 1, 8))


def test_regular_session_times_in_utc() -> None:
    # Winter (EST, UTC-5) and summer (EDT, UTC-4).
    assert session_open_utc(dt.date(2024, 1, 8)) == pd.Timestamp("2024-01-08 14:30", tz="UTC")
    assert session_close_utc(dt.date(2024, 1, 8)) == pd.Timestamp("2024-01-08 21:00", tz="UTC")
    assert session_close_utc(dt.date(2024, 7, 8)) == pd.Timestamp("2024-07-08 20:00", tz="UTC")
    assert session_close_utc(dt.date(2024, 11, 29)) == pd.Timestamp("2024-11-29 18:00", tz="UTC")


def test_non_session_dates_get_regular_hours() -> None:
    # Synthetic data uses every weekday; a holiday in it keeps 09:30-16:00.
    assert session_open_utc(dt.date(2024, 1, 15)) == pd.Timestamp("2024-01-15 14:30", tz="UTC")
    assert session_close_utc(dt.date(2024, 1, 15)) == pd.Timestamp("2024-01-15 21:00", tz="UTC")


def test_vectorised_times_match_scalar_ones() -> None:
    dates = pd.bdate_range("2024-11-20", "2025-01-10")
    closes = session_closes_utc(dates)
    opens = session_opens_utc(dates)
    assert list(closes) == [session_close_utc(d) for d in dates]
    assert list(opens) == [session_open_utc(d) for d in dates]
    assert closes.tz is not None and str(closes.tz) == "UTC"


def test_next_and_previous_session_skip_holidays() -> None:
    assert next_session(dt.date(2024, 1, 12)) == dt.date(2024, 1, 16)  # over MLK weekend
    assert next_session(dt.date(2024, 3, 28)) == dt.date(2024, 4, 1)  # over Good Friday
    assert next_session(dt.date(2001, 9, 10)) == dt.date(2001, 9, 17)
    assert next_session(dt.date(2024, 1, 13)) == dt.date(2024, 1, 16)  # from a weekend
    assert previous_session(dt.date(2024, 1, 16)) == dt.date(2024, 1, 12)
    assert previous_session(dt.date(2024, 12, 26)) == dt.date(2024, 12, 24)


def test_sessions_between_is_inclusive_and_skips_holidays() -> None:
    days = sessions_between(dt.date(2024, 12, 23), dt.date(2024, 12, 27))
    assert [d.date().isoformat() for d in days] == [
        "2024-12-23",
        "2024-12-24",
        "2024-12-26",
        "2024-12-27",
    ]
    assert days.tz is None


def test_last_completed_session() -> None:
    # Before Monday's close, the last completed session is the Friday before.
    assert last_completed_session(dt.datetime(2024, 1, 8, 20, 59, tzinfo=UTC)) == dt.date(
        2024, 1, 5
    )
    assert last_completed_session(dt.datetime(2024, 1, 8, 21, 0, tzinfo=UTC)) == dt.date(2024, 1, 8)
    # Thanksgiving day: Wednesday was the last session.
    assert last_completed_session(dt.datetime(2024, 11, 28, 22, 0, tzinfo=UTC)) == dt.date(
        2024, 11, 27
    )
    # The day after Thanksgiving closes at 13:00 New York (18:00 UTC).
    assert last_completed_session(dt.datetime(2024, 11, 29, 18, 0, tzinfo=UTC)) == dt.date(
        2024, 11, 29
    )
    with pytest.raises(ValueError, match="timezone-aware"):
        last_completed_session(dt.datetime(2024, 1, 8, 22, 0))


def test_assign_sessions_respects_early_close() -> None:
    dates = sessions_between(dt.date(2024, 11, 27), dt.date(2024, 12, 2))
    times = pd.Series(
        pd.to_datetime(
            [
                "2024-11-29 17:59",  # before the 13:00 New York close
                "2024-11-29 18:01",  # after it: counts toward the next session
                "2024-11-28 15:00",  # Thanksgiving: counts toward Friday
            ],
            utc=True,
        )
    )
    positions = assign_sessions(times, dates)
    assert [dates[p].date().isoformat() for p in positions] == [
        "2024-11-29",
        "2024-12-02",
        "2024-11-29",
    ]


def test_dates_outside_the_calendar_raise() -> None:
    too_early = CALENDAR_START - dt.timedelta(days=1)
    too_late = CALENDAR_END + dt.timedelta(days=1)
    with pytest.raises(ValueError, match="outside the NYSE calendar"):
        is_session(too_early)
    with pytest.raises(ValueError, match="outside the NYSE calendar"):
        session_close_utc(too_late)
    with pytest.raises(ValueError, match="outside the NYSE calendar"):
        session_closes_utc(pd.DatetimeIndex([pd.Timestamp(too_early)]))
