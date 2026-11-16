import os
import sys
from datetime import datetime

# Set path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.services.backtest_engine import run_backtest_with_baselines
from app.services.memo_generator import create_client_memo_pdf

os.makedirs("reports/memos", exist_ok=True)

# 3 Strategic Configurations
configs = [
    {
        "name": "aggressive",
        "params": {
            "initial_capital": 100000.0,
            "min_trade_amount": 10.0,
            "max_position_weight": 0.40,       # 40% single-stock exposure cap
            "cash_reserve_floor": 0.05,         # 5% cash floor
            "base_allocation_pct": 0.15,        # 15% base allocation
            "stop_loss_pct": 0.07,              # 7% stop-loss
            "take_profit_pct": 0.25,            # 25% take-profit
            "transaction_cost_bps": 10.0
        }
    },
    {
        "name": "conservative",
        "params": {
            "initial_capital": 100000.0,
            "min_trade_amount": 10.0,
            "max_position_weight": 0.20,       # 20% single-stock cap
            "cash_reserve_floor": 0.20,         # 20% cash floor
            "base_allocation_pct": 0.05,        # 5% base allocation
            "stop_loss_pct": 0.03,              # 3% stop-loss
            "take_profit_pct": 0.10,            # 10% take-profit
            "transaction_cost_bps": 10.0
        }
    },
    {
        "name": "moderate_balanced",
        "params": {
            "initial_capital": 100000.0,
            "min_trade_amount": 10.0,
            "max_position_weight": 0.30,       # 30% single-stock cap
            "cash_reserve_floor": 0.10,         # 10% cash floor
            "base_allocation_pct": 0.10,        # 10% base allocation
            "stop_loss_pct": 0.05,              # 5% stop-loss
            "take_profit_pct": 0.15,            # 15% take-profit
            "transaction_cost_bps": 10.0
        }
    }
]

print("Starting generation of 3 distinct advisory client memos...")

for cfg in configs:
    name = cfg["name"]
    params = cfg["params"]
    print(f"\nRunning backtest simulation for '{name}' configuration...")
    res = run_backtest_with_baselines("PORTFOLIO", params)
    
    # Format stats
    data_summary = {
        "strategy_return": res["strategy"]["total_return_pct"],
        "benchmark_return": res["benchmark_basket"]["total_return_pct"],
        "spy_return": res["benchmark_spy"]["total_return_pct"],
        "sharpe": res["strategy"]["sharpe_ratio"],
        "sortino": res["strategy"]["sortino_ratio"],
        "max_dd": res["strategy"]["max_drawdown_pct"],
        "trades_count": res["strategy"]["trades_count"],
        "win_rate": res["strategy"]["win_rate"],
        "mc_percentile": res["monte_carlo_sharpe_percentile"],
        "cagr": res["strategy"]["cagr"],
        "trades": res["trades"]
    }
    
    filename = f"client_memo_{name}.pdf"
    print(f"Generating PDF memo '{filename}'...")
    filepath = create_client_memo_pdf(data_summary, filename)
    print(f"Saved: {filepath}")
    print(f"Strategy Return: {data_summary['strategy_return']:.2f}% | Sharpe: {data_summary['sharpe']:.2f} | Drawdown: {data_summary['max_dd']:.2f}%")

print("\nSuccessfully generated all 3 memos!")
