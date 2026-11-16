from __future__ import annotations

import pandas as pd
import pytest

from signal_audit.audit.backtest import BacktestConfig, run_backtest, target_weights
from signal_audit.data.market import MarketData
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


def test_config_validation() -> None:
    with pytest.raises(ValueError):
        BacktestConfig(top_k=0)
    with pytest.raises(ValueError):
        BacktestConfig(cost_bps=-1.0)
