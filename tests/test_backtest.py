from __future__ import annotations

import pandas as pd
import pytest

from signal_audit.audit.backtest import (
    BacktestConfig,
    holding_periods,
    run_backtest,
    target_weights,
)
from signal_audit.data.market import MarketData
from signal_audit.signals.examples import MomentumSignal
from tests.conftest import constant_prices


def _jump_market() -> MarketData:
    """Ticker A's open rises 10% between sessions 5 and 6. Nothing else moves."""
    data = constant_prices()
    opens = data.opens.copy()
    opens.iloc[6:, 0] = 110.0
    return MarketData(opens=opens, closes=opens.copy())


def _score_only_on(data: MarketData, session: int) -> pd.DataFrame:
    scores = pd.DataFrame(float("nan"), index=data.dates, columns=data.tickers)
    scores.iloc[session, 0] = 1.0
    return scores


def test_score_at_close_t_is_filled_at_open_t_plus_1() -> None:
    data = _jump_market()
    config = BacktestConfig(top_k=1, cost_bps=0.0)

    # Scored at the close of session 4, entered at the open of 5, so it earns
    # the open-5 to open-6 jump.
    early = run_backtest(_score_only_on(data, 4), data, config)
    assert early.returns.iloc[5] == pytest.approx(0.10)
    assert early.returns.sum() == pytest.approx(0.10)

    # Scored at the close of session 5: entered at the open of 6, after the jump.
    late = run_backtest(_score_only_on(data, 5), data, config)
    assert late.returns.abs().sum() == pytest.approx(0.0)


def test_costs_are_charged_on_turnover_only() -> None:
    data = constant_prices()
    scores = pd.DataFrame(0.0, index=data.dates, columns=data.tickers)
    scores["A"] = 1.0  # always hold A

    result = run_backtest(scores, data, BacktestConfig(top_k=1, cost_bps=10.0))
    # One buy of 100% of the portfolio at 10 bps, then no further trading.
    assert result.turnover.sum() == pytest.approx(1.0)
    assert result.returns.sum() == pytest.approx(-0.001)


def test_last_session_is_dropped() -> None:
    data = constant_prices(n_days=10)
    scores = pd.DataFrame(1.0, index=data.dates, columns=data.tickers)
    result = run_backtest(scores, data, BacktestConfig(top_k=1))
    assert len(result.returns) == 9


def test_target_weights_leave_cash_when_few_scores() -> None:
    scores = pd.DataFrame({"A": [1.0], "B": [float("nan")], "C": [float("nan")]})
    weights = target_weights(scores, top_k=2)
    assert weights.iloc[0].tolist() == [0.5, 0.0, 0.0]


def test_holding_periods_match_a_direct_calculation(market: MarketData) -> None:
    scores = MomentumSignal().compute(market)
    config = BacktestConfig(top_k=3, cost_bps=10.0)
    periods = holding_periods(scores, market, config)

    weights = target_weights(scores, 3)
    for pos in (30, 31, 200):
        decided = market.dates[pos]
        period = periods[decided]
        assert period.entered == market.dates[pos + 1]
        assert period.exited == market.dates[pos + 2]
        held = weights.iloc[pos]
        forward = market.opens.iloc[pos + 2] / market.opens.iloc[pos + 1] - 1.0
        gross = float((held * forward).sum())
        turnover = float((held - weights.iloc[pos - 1]).abs().sum())
        assert period.gross_return == pytest.approx(gross)
        assert period.turnover == pytest.approx(turnover)
        assert period.net_return == pytest.approx(gross - turnover * 10.0 / 10_000)
        assert list(period.weights.index) == list(held[held > 0].index)
        assert period.ticker_returns.to_dict() == pytest.approx(
            forward[held[held > 0].index].to_dict()
        )


def test_holding_periods_agree_with_run_backtest(market: MarketData) -> None:
    scores = MomentumSignal().compute(market)
    config = BacktestConfig(top_k=2, cost_bps=25.0)
    result = run_backtest(scores, market, config)
    for period in holding_periods(scores, market, config).values():
        assert period.net_return == pytest.approx(result.returns.loc[period.entered])
        assert period.gross_return == pytest.approx(result.gross_returns.loc[period.entered])


def test_holding_periods_for_sparse_rows() -> None:
    data = _jump_market()
    scores = pd.DataFrame({"A": [1.0, 1.0]}, index=data.dates[[3, 4]])
    periods = holding_periods(scores, data, BacktestConfig(top_k=1, cost_bps=10.0))
    assert set(periods) == {data.dates[3], data.dates[4]}
    # Entered from cash: the whole portfolio is bought.
    assert periods[data.dates[3]].turnover == pytest.approx(1.0)
    # Already held A from the session before: nothing to trade.
    assert periods[data.dates[4]].turnover == pytest.approx(0.0)
    assert periods[data.dates[4]].gross_return == pytest.approx(0.10)
    assert periods[data.dates[4]].net_return == pytest.approx(0.10)


def test_holding_periods_skip_rows_without_an_exit() -> None:
    data = constant_prices(n_days=10)
    scores = pd.DataFrame(1.0, index=data.dates, columns=data.tickers)
    periods = holding_periods(scores, data, BacktestConfig(top_k=1))
    assert data.dates[7] in periods
    assert data.dates[8] not in periods
    assert data.dates[9] not in periods


def test_config_validation() -> None:
    with pytest.raises(ValueError):
        BacktestConfig(top_k=0)
    with pytest.raises(ValueError):
        BacktestConfig(cost_bps=-1.0)
