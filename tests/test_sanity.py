from __future__ import annotations

import numpy as np
import pandas as pd

from signal_audit.data.market import MarketData
from signal_audit.data.sanity import KINDS, PriceIssue, SanityReport, check_prices
from tests.conftest import constant_prices


def _with(data: MarketData, *, opens: pd.DataFrame, closes: pd.DataFrame) -> MarketData:
    return MarketData(opens=opens, closes=closes)


def test_clean_synthetic_data_passes(market: MarketData) -> None:
    report = check_prices(market)
    assert report.passed
    assert report.issues == ()
    assert report.n_sessions == len(market.dates)
    assert report.n_tickers == len(market.tickers)
    for kind in KINDS:
        assert report.count(kind) == 0


def test_non_positive_price_is_caught_and_fails() -> None:
    data = constant_prices()
    closes = data.closes.copy()
    closes.iloc[3, 1] = -5.0
    opens = data.opens.copy()
    opens.iloc[3, 1] = 0.0  # same ticker-day: still one issue
    report = check_prices(_with(data, opens=opens, closes=closes))
    assert report.count("non_positive") == 1
    issue = report.issues[0]
    assert issue.ticker == "B"
    assert issue.date == data.dates[3]
    assert not report.passed


def test_missing_counts_only_after_first_valid_price() -> None:
    data = constant_prices(n_days=12)
    opens, closes = data.opens.copy(), data.closes.copy()
    opens.iloc[:4, 0] = np.nan  # leading NaNs: ticker A starts late
    closes.iloc[:4, 0] = np.nan
    closes.iloc[7, 2] = np.nan  # hole in C
    opens.iloc[9, 2] = np.nan
    report = check_prices(_with(data, opens=opens, closes=closes))
    assert report.count("missing") == 2
    assert {i.ticker for i in report.issues if i.kind == "missing"} == {"C"}
    assert report.passed  # missing data is reported but does not fail


def test_two_to_one_unadjusted_split_is_flagged() -> None:
    data = constant_prices()
    opens, closes = data.opens.copy(), data.closes.copy()
    opens.iloc[5:, 0] = 50.0
    closes.iloc[5:, 0] = 50.0
    report = check_prices(_with(data, opens=opens, closes=closes))
    assert report.count("split_suspect") == 1
    issue = next(i for i in report.issues if i.kind == "split_suspect")
    assert issue.ticker == "A"
    assert issue.date == data.dates[5]
    assert "0.500" in issue.detail
    assert not report.passed


def test_crash_not_near_split_ratio_is_not_flagged() -> None:
    data = constant_prices()
    opens, closes = data.opens.copy(), data.closes.copy()
    opens.iloc[5:, 0] = 60.0  # ratio 0.6: >30% move, but >5% from 2/3 and 3/4
    closes.iloc[5:, 0] = 60.0
    report = check_prices(_with(data, opens=opens, closes=closes))
    assert report.count("split_suspect") == 0
    assert report.passed


def test_small_move_near_split_ratio_is_not_flagged() -> None:
    data = constant_prices()
    opens, closes = data.opens.copy(), data.closes.copy()
    opens.iloc[5:, 0] = 75.0  # ratio 0.75 is a move of only 25%
    closes.iloc[5:, 0] = 75.0
    assert check_prices(_with(data, opens=opens, closes=closes)).count("split_suspect") == 0
    assert (
        check_prices(_with(data, opens=opens, closes=closes), split_move=0.2).count("split_suspect")
        == 1
    )


def test_close_to_close_split_is_flagged() -> None:
    data = constant_prices()
    closes = data.closes.copy()
    closes.iloc[5:, 1] = 300.0  # open stays flat; close triples
    report = check_prices(_with(data, opens=data.opens, closes=closes))
    assert report.count("split_suspect") >= 1
    assert report.issues[0].ticker == "B"


def _frame_with_dates(dates: pd.DatetimeIndex) -> MarketData:
    frame = pd.DataFrame(100.0, index=dates, columns=["A"])
    return MarketData(opens=frame.copy(), closes=frame.copy())


def test_four_weekday_gap_not_flagged_five_is_() -> None:
    # Missing Tue-Fri (4 weekdays) between Mon 2001-09-10 and Mon 2001-09-17.
    four = pd.DatetimeIndex(["2001-09-07", "2001-09-10", "2001-09-17", "2001-09-18"])
    assert check_prices(_frame_with_dates(four)).count("calendar_gap") == 0
    # Missing Tue-Mon (5 weekdays: Tue, Wed, Thu, Fri, Mon).
    five = pd.DatetimeIndex(["2001-09-07", "2001-09-10", "2001-09-18", "2001-09-19"])
    report = check_prices(_frame_with_dates(five))
    assert report.count("calendar_gap") == 1
    gap = report.issues[0]
    assert gap.ticker is None
    assert gap.date == pd.Timestamp("2001-09-11")
    assert "5 weekdays" in gap.detail
    assert report.passed  # gaps are reported but do not fail


def test_ordinary_holiday_is_not_a_gap() -> None:
    dates = pd.DatetimeIndex(["2024-01-12", "2024-01-16"])  # MLK weekend
    assert check_prices(_frame_with_dates(dates)).count("calendar_gap") == 0


def test_to_lines_one_line_per_check_with_zero_counts() -> None:
    lines = check_prices(constant_prices()).to_lines()
    assert len(lines) == 5
    assert lines[0] == "Sessions: 10, tickers: 3"
    assert lines[1] == "Non-positive prices: 0"
    assert lines[2] == "Missing ticker-days: 0"
    assert lines[3].endswith(": 0")
    assert lines[4].startswith("Split suspects: 0")


def test_to_lines_mentions_first_issue() -> None:
    data = constant_prices()
    closes = data.closes.copy()
    closes.iloc[4, 2] = np.nan
    lines = check_prices(_with(data, opens=data.opens, closes=closes)).to_lines()
    assert lines[2] == f"Missing ticker-days: 1 (first: {data.dates[4]:%Y-%m-%d} C)"


def test_passed_semantics_from_issues() -> None:
    ts = pd.Timestamp("2024-01-02")

    def report(kind: str) -> SanityReport:
        return SanityReport(1, 1, (PriceIssue(kind, "A", ts, "x"),))

    assert report("missing").passed
    assert report("calendar_gap").passed
    assert not report("non_positive").passed
    assert not report("split_suspect").passed
    assert report("missing").count("missing") == 1
    assert report("missing").count("non_positive") == 0
