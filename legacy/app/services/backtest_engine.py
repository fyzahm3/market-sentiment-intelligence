import os
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, List, Tuple
from app.core.config import settings
from app.services.decision_engine import decide_trade

def calculate_metrics(equity_curve: pd.Series, trades_log: List[Dict]) -> Dict:
    """
    Computes performance metrics: CAGR, Sharpe, Sortino, Max Drawdown, Win Rate.
    """
    if equity_curve.empty or len(equity_curve) < 2:
        return {
            "total_return_pct": 0.0,
            "cagr": 0.0,
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "max_drawdown_pct": 0.0,
            "win_rate": 0.0,
            "trades_count": 0
        }

    initial_val = equity_curve.iloc[0]
    final_val = equity_curve.iloc[-1]
    
    total_return = (final_val - initial_val) / initial_val * 100
    
    # CAGR calculation (assuming daily steps and 252 trading days/year)
    days = len(equity_curve)
    cagr = ((final_val / initial_val) ** (252.0 / days) - 1.0) * 100 if final_val > 0 and initial_val > 0 else 0.0
    
    daily_returns = equity_curve.pct_change().dropna()
    
    # Sharpe Ratio (annualized, risk-free rate assumed = 0)
    std = daily_returns.std()
    mean = daily_returns.mean()
    sharpe = (mean / std) * np.sqrt(252) if std > 0 else 0.0
    
    # Sortino Ratio (annualized, using downside standard deviation)
    downside_returns = daily_returns[daily_returns < 0]
    downside_std = downside_returns.std()
    sortino = (mean / downside_std) * np.sqrt(252) if downside_std > 0 else 0.0
    
    # Max Drawdown
    cum_max = equity_curve.cummax()
    drawdowns = (equity_curve - cum_max) / cum_max * 100
    max_dd = drawdowns.min()
    
    # Win Rate of trades
    win_rate = 0.0
    if trades_log:
        buy_trades = {}
        completed_trades = []
        for t in trades_log:
            sym = t["symbol"]
            act = t["action"]
            price = t["price"]
            qty = t["quantity"]
            if act == "BUY":
                buy_trades[sym] = buy_trades.get(sym, []) + [(price, qty)]
            elif act == "SELL":
                # Average buy cost
                buys = buy_trades.get(sym, [])
                if buys:
                    total_cost = sum(p * q for p, q in buys)
                    total_qty = sum(q for p, q in buys)
                    avg_cost = total_cost / total_qty if total_qty > 0 else 0.0
                    pnl = (price - avg_cost) / avg_cost if avg_cost > 0 else 0.0
                    completed_trades.append(pnl > 0)
                    buy_trades[sym] = []
        if completed_trades:
            win_rate = sum(completed_trades) / len(completed_trades) * 100
        else:
            win_rate = (daily_returns > 0).mean() * 100  # Fallback to positive daily return pct

    return {
        "total_return_pct": float(total_return),
        "cagr": float(cagr),
        "sharpe_ratio": float(sharpe),
        "sortino_ratio": float(sortino),
        "max_drawdown_pct": float(max_dd),
        "win_rate": float(win_rate),
        "trades_count": len(trades_log)
    }

def run_backtest_simulation(
    symbol_or_portfolio: str,
    params: Dict,
    shuffle_signals: bool = False
) -> Tuple[pd.Series, List[Dict]]:
    """
    Runs the event-driven backtest simulation.
    If shuffle_signals is True, it shuffles daily sentiment signals (for Monte Carlo).
    """
    prices_file = "data/historical_prices.parquet"
    sentiment_file = "data/historical_sentiment.parquet"
    
    if not os.path.exists(prices_file) or not os.path.exists(sentiment_file):
        raise FileNotFoundError("Backtest Parquet files are missing. Please run scripts/download_backtest_data.py first.")

    prices_df = pd.read_parquet(prices_file)
    sentiment_df = pd.read_parquet(sentiment_file)
    
    tickers = settings.target_stock_list
    if symbol_or_portfolio != "PORTFOLIO" and symbol_or_portfolio != "ALL":
        target_tickers = [symbol_or_portfolio]
        params = params.copy()
        params["max_position_weight"] = 1.0
        params["cash_reserve_floor"] = 0.0
    else:
        target_tickers = tickers
        
    # Get overlapping dates
    prices_df = prices_df[prices_df["symbol"].isin(target_tickers)].copy()
    sentiment_df = sentiment_df[sentiment_df["symbol"].isin(target_tickers)].copy()
    
    # Sort and get unique trading dates
    unique_dates = sorted(list(prices_df["Date"].unique()))
    if not unique_dates:
        return pd.Series(), []
        
    # Walk-forward split: Tune on first 35% of the dates, backtest on remaining 65%
    split_idx = int(len(unique_dates) * 0.35)
    test_dates = unique_dates[split_idx:]
    
    # Pivot prices for fast daily access
    price_pivot = prices_df.pivot(index="Date", columns="symbol")
    
    # Prepare sentiment dictionary
    sentiment_df["Date"] = pd.to_datetime(sentiment_df["date"]).dt.date
    if shuffle_signals:
        # Shuffle dates to break correlation with actual return dates
        shuffled_dates = np.random.permutation(sentiment_df["Date"].values)
        sentiment_df["Date"] = shuffled_dates
        
    sentiment_pivot = sentiment_df.pivot(index="Date", columns="symbol")
    
    # Portfolio State
    initial_capital = params.get("initial_capital", 100000.0)
    cash = initial_capital
    positions = {t: 0.0 for t in target_tickers}
    avg_buy_prices = {t: 0.0 for t in target_tickers}
    
    equity_curve = {}
    trades_log = []
    
    # 5-day rolling return calculation for trend predictive direction
    close_pivot = price_pivot["Close"]
    rolling_ma_5 = close_pivot.rolling(window=5).mean()
    
    for i, date in enumerate(test_dates):
        # 1. Update Portfolio Value at the start of day (using prior day's close for portfolio sizing checks)
        stock_value = 0.0
        for sym in target_tickers:
            if positions[sym] > 0:
                # Get Close price of yesterday
                close_col = price_pivot["Close"][sym]
                # Fallback to current date price if yesterday's price is not available
                prev_date = test_dates[i-1] if i > 0 else date
                close_price = close_col.get(prev_date, close_col.get(date, 0.0))
                stock_value += positions[sym] * close_price
        portfolio_val = cash + stock_value
        
        # 2. Check risk exits (Stop Loss / Take Profit / Bearish exits) using today's open price
        # If exit occurs, trade executes at today's open price
        for sym in target_tickers:
            if positions[sym] > 0:
                open_price = price_pivot["Open"][sym].get(date, 0.0)
                if open_price == 0.0:
                    continue
                    
                # Get daily sentiment score
                vader_score = sentiment_pivot["vader_score"][sym].get(date, 0.0) if sym in sentiment_pivot["vader_score"].columns else 0.0
                finbert_score = sentiment_pivot["finbert_score"][sym].get(date, 0.0) if sym in sentiment_pivot["finbert_score"].columns else 0.0
                hybrid_score = sentiment_pivot["hybrid_score"][sym].get(date, 0.0) if sym in sentiment_pivot["hybrid_score"].columns else 0.0
                
                if hybrid_score >= settings.sentiment_neutral_band:
                    sentiment_label = "bullish"
                elif hybrid_score <= -settings.sentiment_neutral_band:
                    sentiment_label = "bearish"
                else:
                    sentiment_label = "neutral"
                
                # Check exit using decide_trade (will evaluate stop-loss, take-profit, bearish exit)
                exit_check = decide_trade(
                    symbol=sym,
                    position_qty=positions[sym],
                    avg_buy_price=avg_buy_prices[sym],
                    current_price=open_price,
                    sentiment_label=sentiment_label,
                    hybrid_score=hybrid_score,
                    prediction_direction="up",  # UP to bypass entry triggers (we only test exit here)
                    cash_balance=cash,
                    total_portfolio_value=portfolio_val,
                    params=params
                )
                
                if exit_check and exit_check["action"] == "SELL":
                    # Execute sell at today's Open price
                    sell_qty = exit_check["quantity"]
                    revenue = sell_qty * open_price
                    # Deduct transaction cost (10 bps)
                    tx_cost = revenue * (params.get("transaction_cost_bps", 10.0) / 10000.0)
                    cash += (revenue - tx_cost)
                    
                    trades_log.append({
                        "date": date.strftime("%Y-%m-%d"),
                        "symbol": sym,
                        "action": "SELL",
                        "quantity": float(sell_qty),
                        "price": float(open_price),
                        "cost": float(tx_cost),
                        "reason": exit_check["reason"]
                    })
                    
                    positions[sym] = 0.0
                    avg_buy_prices[sym] = 0.0
                    # Update portfolio value
                    portfolio_val = cash + sum(positions[s] * price_pivot["Close"][s].get(date, 0.0) for s in target_tickers if positions[s] > 0)
        
        # 3. Check entry signals (BUY) using today's open price
        for sym in target_tickers:
            open_price = price_pivot["Open"][sym].get(date, 0.0)
            close_price = price_pivot["Close"][sym].get(date, 0.0)
            if open_price == 0.0 or close_price == 0.0:
                continue
                
            # Get daily sentiment score
            vader_score = sentiment_pivot["vader_score"][sym].get(date, 0.0) if sym in sentiment_pivot["vader_score"].columns else 0.0
            finbert_score = sentiment_pivot["finbert_score"][sym].get(date, 0.0) if sym in sentiment_pivot["finbert_score"].columns else 0.0
            hybrid_score = sentiment_pivot["hybrid_score"][sym].get(date, 0.0) if sym in sentiment_pivot["hybrid_score"].columns else 0.0
            
            if hybrid_score >= settings.sentiment_neutral_band:
                sentiment_label = "bullish"
            elif hybrid_score <= -settings.sentiment_neutral_band:
                sentiment_label = "bearish"
            else:
                sentiment_label = "neutral"
                
            # Trend direction check (rolling moving average indicator)
            # Predict UP if close is above 5-day MA
            ma_val = rolling_ma_5[sym].get(date, 0.0)
            prediction_direction = "up" if close_price > ma_val and ma_val > 0 else "down"
            
            # Check entry using decide_trade
            entry_check = decide_trade(
                symbol=sym,
                position_qty=positions[sym],
                avg_buy_price=avg_buy_prices[sym],
                current_price=open_price,
                sentiment_label=sentiment_label,
                hybrid_score=hybrid_score,
                prediction_direction=prediction_direction,
                cash_balance=cash,
                total_portfolio_value=portfolio_val,
                params=params
            )
            
            if entry_check and entry_check["action"] == "BUY":
                buy_qty = entry_check["quantity"]
                cost = buy_qty * open_price
                tx_cost = cost * (params.get("transaction_cost_bps", 10.0) / 10000.0)
                
                if cash >= (cost + tx_cost):
                    cash -= (cost + tx_cost)
                    old_qty = positions[sym]
                    old_price = avg_buy_prices[sym]
                    new_qty = old_qty + buy_qty
                    new_avg = ((old_qty * old_price) + cost) / new_qty if new_qty > 0 else 0.0
                    
                    positions[sym] = new_qty
                    avg_buy_prices[sym] = new_avg
                    
                    trades_log.append({
                        "date": date.strftime("%Y-%m-%d"),
                        "symbol": sym,
                        "action": "BUY",
                        "quantity": float(buy_qty),
                        "price": float(open_price),
                        "cost": float(tx_cost),
                        "reason": entry_check["reason"]
                    })
                    # Update portfolio value
                    portfolio_val = cash + sum(positions[s] * price_pivot["Close"][s].get(date, 0.0) for s in target_tickers if positions[s] > 0)
        
        # 4. Mark to market at the end of the day (using Close price of today)
        daily_equity = cash
        for sym in target_tickers:
            if positions[sym] > 0:
                close_price = price_pivot["Close"][sym].get(date, 0.0)
                daily_equity += positions[sym] * close_price
        equity_curve[date] = daily_equity

    # Convert equity curve to series
    equity_series = pd.Series(equity_curve)
    return equity_series, trades_log

def run_backtest_with_baselines(symbol_or_portfolio: str, params: Dict) -> Dict:
    """
    Runs backtest and calculates metrics for:
    1. Strategy
    2. Equal-Weight Buy-and-Hold
    3. SPY Buy-and-Hold
    4. Monte Carlo percentile rank
    """
    # 1. Strategy
    equity_curve, trades = run_backtest_simulation(symbol_or_portfolio, params, shuffle_signals=False)
    metrics = calculate_metrics(equity_curve, trades)
    
    # Convert dates to standard strings for JSON transfer
    equity_curve_dict = {k.strftime("%Y-%m-%d"): v for k, v in equity_curve.items()}
    
    # 2. Benchmarks
    # We load price parquet files to calculate buy-and-hold benchmarks
    prices_file = "data/historical_prices.parquet"
    prices_df = pd.read_parquet(prices_file)
    
    tickers = settings.target_stock_list
    if symbol_or_portfolio != "PORTFOLIO" and symbol_or_portfolio != "ALL":
        target_tickers = [symbol_or_portfolio]
    else:
        target_tickers = tickers
        
    prices_df = prices_df[prices_df["symbol"].isin(target_tickers)].copy()
    unique_dates = sorted(list(prices_df["Date"].unique()))
    split_idx = int(len(unique_dates) * 0.35)
    test_dates = unique_dates[split_idx:]
    
    # Pivot prices
    price_pivot = prices_df.pivot(index="Date", columns="symbol")
    close_pivot = price_pivot["Close"].loc[test_dates]
    
    # Equal Weight Benchmark Basket
    norm_closes = close_pivot / close_pivot.iloc[0]
    bench_basket = norm_closes.mean(axis=1) * params.get("initial_capital", 100000.0)
    bench_basket_metrics = calculate_metrics(bench_basket, [])
    bench_basket_curve = {k.strftime("%Y-%m-%d"): v for k, v in bench_basket.items()}
    
    # SPY Benchmark
    all_prices = pd.read_parquet(prices_file)
    spy_df = all_prices[all_prices["symbol"] == "SPY"].copy()
    spy_df = spy_df[spy_df["Date"].isin(test_dates)].sort_values("Date")
    spy_close = spy_df.set_index("Date")["Close"]
    spy_bench = (spy_close / spy_close.iloc[0]) * params.get("initial_capital", 100000.0)
    spy_metrics = calculate_metrics(spy_bench, [])
    spy_curve = {k.strftime("%Y-%m-%d"): v for k, v in spy_bench.items()}

    # 3. Monte Carlo shuffled-signal baselines (N=1000 shuffled runs)
    print("Running Monte Carlo N=1000 shuffled-signal runs...")
    monte_carlo_sharpes = []
    
    for _ in range(1000):
        try:
            mc_equity, _ = run_backtest_simulation(symbol_or_portfolio, params, shuffle_signals=True)
            mc_metrics = calculate_metrics(mc_equity, [])
            monte_carlo_sharpes.append(mc_metrics["sharpe_ratio"])
        except Exception:
            pass
            
    strategy_sharpe = metrics["sharpe_ratio"]
    if monte_carlo_sharpes:
        percentile = (np.array(monte_carlo_sharpes) < strategy_sharpe).mean() * 100
    else:
        percentile = 50.0

    return {
        "ticker": symbol_or_portfolio,
        "strategy": metrics,
        "benchmark_basket": bench_basket_metrics,
        "benchmark_spy": spy_metrics,
        "monte_carlo_sharpe_percentile": float(percentile),
        "curves": {
            "strategy": equity_curve_dict,
            "benchmark_basket": bench_basket_curve,
            "benchmark_spy": spy_curve
        },
        "trades": trades
    }
