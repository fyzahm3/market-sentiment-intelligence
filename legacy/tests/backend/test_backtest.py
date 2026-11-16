import os
import pytest
from app.services.backtest_engine import run_backtest_with_baselines

@pytest.mark.skipif(not os.path.exists("data/historical_prices.parquet"), reason="Parquet data files not generated yet")
def test_backtest_runs_successfully():
    params = {
        "initial_capital": 100000.0,
        "min_trade_amount": 10.0,
        "max_position_weight": 0.30,
        "cash_reserve_floor": 0.10,
        "base_allocation_pct": 0.10,
        "stop_loss_pct": 0.05,
        "take_profit_pct": 0.15,
        "transaction_cost_bps": 10.0
    }
    
    # Run backtest for portfolio
    res = run_backtest_with_baselines("PORTFOLIO", params)
    
    assert res is not None
    assert res["ticker"] == "PORTFOLIO"
    assert "strategy" in res
    assert "benchmark_basket" in res
    assert "benchmark_spy" in res
    assert "curves" in res
    assert "trades" in res
    
    # Check shape of curves
    assert len(res["curves"]["strategy"]) > 0
    assert len(res["curves"]["benchmark_basket"]) > 0
    assert len(res["curves"]["benchmark_spy"]) > 0
    
    # Check that Monte Carlo percentile is calculated and valid
    assert 0.0 <= res["monte_carlo_sharpe_percentile"] <= 100.0
