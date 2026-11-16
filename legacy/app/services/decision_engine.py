from typing import Dict, Optional

def decide_trade(
    symbol: str,
    position_qty: float,
    avg_buy_price: float,
    current_price: float,
    sentiment_label: str,
    hybrid_score: float,
    prediction_direction: str,
    cash_balance: float,
    total_portfolio_value: float,
    params: Dict
) -> Optional[Dict]:
    """
    Shared decision logic for paper trading and backtesting.
    Returns a dict with trade action and metadata, or None if no action is taken.
    """
    # 1. RISK MANAGEMENT: EXIT CHECKS (only if we hold a position)
    if position_qty > 0.0001:
        # A. Stop-Loss
        stop_loss_price = avg_buy_price * (1.0 - params.get("stop_loss_pct", 0.05))
        if current_price <= stop_loss_price:
            return {
                "action": "SELL",
                "quantity": position_qty,
                "reason": f"Stop-loss triggered: Price {current_price:.2f} <= SL {stop_loss_price:.2f} (Avg: {avg_buy_price:.2f})"
            }

        # B. Take-Profit
        take_profit_price = avg_buy_price * (1.0 + params.get("take_profit_pct", 0.15))
        if current_price >= take_profit_price:
            return {
                "action": "SELL",
                "quantity": position_qty,
                "reason": f"Take-profit triggered: Price {current_price:.2f} >= TP {take_profit_price:.2f} (Avg: {avg_buy_price:.2f})"
            }

        # C. Bearish Sentiment Exit
        if sentiment_label.lower() == "bearish":
            return {
                "action": "SELL",
                "quantity": position_qty,
                "reason": f"Sentiment exit: Label became BEARISH ({hybrid_score:.2f})"
            }

    # 2. ENTRY CHECKS: BUY SIGNALS
    # Buy when: Sentiment is Bullish, hybrid score exceeds threshold, and predictive direction is UP
    buy_threshold = params.get("sentiment_buy_threshold", 0.10)
    is_bullish = (sentiment_label.lower() == "bullish") or (hybrid_score >= buy_threshold)
    is_pred_up = (prediction_direction.lower() == "up")

    if is_bullish and is_pred_up:
        # A. Portfolio Exposure Cap (max weight per stock, default 30%)
        max_exposure = total_portfolio_value * params.get("max_position_weight", 0.30)
        current_exposure = position_qty * current_price
        allowed_new_exposure = max_exposure - current_exposure
        
        if allowed_new_exposure <= params.get("min_trade_amount", 10.0):
            return None

        # B. Cash Reserve Floor (default 10% cash reserve)
        cash_floor = total_portfolio_value * params.get("cash_reserve_floor", 0.10)
        available_cash = cash_balance - cash_floor
        
        if available_cash <= params.get("min_trade_amount", 10.0):
            return None

        # C. Allocation Sizing: scale allocation by sentiment strength
        # Base allocation is e.g. 10% of portfolio, scaled by compound hybrid score
        base_alloc = total_portfolio_value * params.get("base_allocation_pct", 0.10)
        target_allocation = base_alloc * hybrid_score

        # Apply constraints
        allocation = min(target_allocation, allowed_new_exposure, available_cash)
        
        if allocation >= params.get("min_trade_amount", 10.0):
            qty_to_buy = allocation / current_price
            return {
                "action": "BUY",
                "quantity": qty_to_buy,
                "reason": f"Entry signal: Sentiment Bullish ({hybrid_score:.2f}), Predict UP. Allocating ${allocation:.2f} ({qty_to_buy:.4f} shares)"
            }

    return None
