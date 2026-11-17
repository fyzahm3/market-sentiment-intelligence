from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from signal_audit.data.market import MarketData
from signal_audit.data.pit import PointInTimeStore
from signal_audit.signals.examples import EngagementSignal
from signal_audit.signals.planted import ArchivedEngagementSignal
from tests.conftest import constant_prices


def _utc(text: str) -> pd.Timestamp:
    return pd.Timestamp(text, tz="UTC")


def _engagement(rows: list[tuple[str, str, str, str, float]]) -> PointInTimeStore:
    """Rows of (ticker, event_time, knowledge_time, post_id, score), times in UTC."""
    return PointInTimeStore(
        pd.DataFrame(
            {
                "ticker": [r[0] for r in rows],
                "event_time": pd.to_datetime([r[1] for r in rows], utc=True),
                "knowledge_time": pd.to_datetime([r[2] for r in rows], utc=True),
                "post_id": [r[3] for r in rows],
                "score": [r[4] for r in rows],
            }
        )
    )


def _with_engagement(store: PointInTimeStore | None) -> MarketData:
    # 2024-01-01 is a Monday; sessions close at 21:00 UTC in January.
    prices = constant_prices(n_days=3, tickers=("AAA", "BBB"))
    return MarketData(opens=prices.opens, closes=prices.closes, engagement=store)


def test_honest_uses_in_session_snapshot_and_leak_uses_final() -> None:
    # One post on Monday with two snapshots before Monday's close and one on Tuesday.
    data = _with_engagement(
        _engagement(
            [
                ("AAA", "2024-01-01 15:00", "2024-01-01 15:05", "p1", 1.0),
                ("AAA", "2024-01-01 15:00", "2024-01-01 20:00", "p1", 5.0),
                ("AAA", "2024-01-01 15:00", "2024-01-02 15:00", "p1", 50.0),
            ]
        )
    )
    monday, tuesday = data.dates[0], data.dates[1]

    honest = EngagementSignal().compute(data)
    leaky = ArchivedEngagementSignal().compute(data)

    assert honest.loc[monday, "AAA"] == pytest.approx(np.log1p(5.0))
    assert leaky.loc[monday, "AAA"] == pytest.approx(np.log1p(50.0))
    # The post belongs to Monday only, and BBB had no posts.
    for scores in (honest, leaky):
        assert scores.loc[tuesday, "AAA"] == 0.0
        assert (scores["BBB"] == 0.0).all()
        assert list(scores.columns) == data.tickers
        assert scores.index.equals(data.dates)


def test_post_counts_on_the_session_of_its_first_snapshot() -> None:
    # Posted Monday but first fetched Tuesday after the close, so it is a Wednesday post.
    data = _with_engagement(
        _engagement(
            [
                ("BBB", "2024-01-01 15:00", "2024-01-02 22:00", "late", 3.0),
                ("BBB", "2024-01-01 15:00", "2024-01-03 15:00", "late", 7.0),
            ]
        )
    )
    honest = EngagementSignal().compute(data)
    assert honest["BBB"].tolist() == pytest.approx([0.0, 0.0, np.log1p(7.0)])


def test_engagement_scores_sum_over_posts() -> None:
    data = _with_engagement(
        _engagement(
            [
                ("AAA", "2024-01-01 15:00", "2024-01-01 16:00", "p1", 2.0),
                ("AAA", "2024-01-01 17:00", "2024-01-01 18:00", "p2", 3.0),
            ]
        )
    )
    honest = EngagementSignal().compute(data)
    assert honest.loc[data.dates[0], "AAA"] == pytest.approx(np.log1p(2.0) + np.log1p(3.0))


@pytest.mark.parametrize("signal", [EngagementSignal(), ArchivedEngagementSignal()])
def test_engagement_signals_have_no_opinion_without_engagement_data(
    signal: EngagementSignal | ArchivedEngagementSignal,
) -> None:
    data = _with_engagement(None)
    scores = signal.compute(data)
    assert scores.index.equals(data.dates)
    assert list(scores.columns) == data.tickers
    assert scores.isna().all().all()


def test_archived_engagement_predicts_the_traded_return_better(market: MarketData) -> None:
    traded = market.opens.shift(-2) / market.opens.shift(-1) - 1.0

    def correlation(scores: pd.DataFrame) -> float:
        # Cross-sectionally demeaned, so only the ranking that drives top-k counts.
        demeaned = scores.sub(scores.mean(axis=1), axis=0)
        returns = traded.sub(traded.mean(axis=1), axis=0)
        pairs = pd.concat([demeaned.stack(), returns.stack()], axis=1).dropna()
        return float(pairs.corr().iloc[0, 1])

    honest = correlation(EngagementSignal().compute(market))
    leaky = correlation(ArchivedEngagementSignal().compute(market))
    assert leaky > 0.1
    assert leaky > honest + 0.05
