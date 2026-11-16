import yfinance as yf
from app.core.config import settings
from app.core.logging import get_logger
from app.db.connection import get_db_connection
from app.services.decision_engine import decide_trade

logger = get_logger("services.trader")

def execute_trade_logic(
    stock_symbol: str,
    hybrid_score: float,
    sentiment_label: str,
    confidence_score: float,
    prediction_confidence: float,
    prediction_direction: str,
):
    """
    Executes live/paper paper-trading actions based on the decision engine.
    Integrates risk exit conditions (Stop Loss, Take Profit) and entry rules.
    """
    logger.info("trade_check", stock=stock_symbol, label=sentiment_label, hybrid=hybrid_score)

    try:
        # Get Real-Time Stock Price
        try:
            ticker = yf.Ticker(stock_symbol)
            current_price = ticker.fast_info.last_price
            if current_price is None:
                hist = ticker.history(period="1d")
                if not hist.empty:
                    current_price = hist['Close'].iloc[-1]
        except Exception as e:
            logger.error("price_fetch_error", error=str(e), stock=stock_symbol)
            return

        if not current_price:
            logger.warning("price_unavailable", stock=stock_symbol)
            return

        # Connect to Database
        with get_db_connection() as conn:
            cur = conn.cursor()

            # 1. Get Cash Balance
            cur.execute("SELECT quantity FROM portfolio WHERE symbol = 'USD'")
            row = cur.fetchone()
            cash_balance = row[0] if row else 0.0

            # 2. Get Stock Position
            cur.execute("SELECT quantity, avg_price FROM portfolio WHERE symbol = %s", (stock_symbol,))
            stock_row = cur.fetchone()
            position_qty = stock_row[0] if stock_row else 0.0
            avg_buy_price = stock_row[1] if stock_row else 0.0

            # 3. Get Total Portfolio Value (Cash + Stock value)
            cur.execute("SELECT symbol, quantity FROM portfolio WHERE asset_type = 'STOCK'")
            holdings = cur.fetchall()
            stock_value = 0.0
            for sym, qty in holdings:
                if qty > 0.0001:
                    try:
                        price = yf.Ticker(sym).fast_info.last_price
                        if not price:
                            price = yf.Ticker(sym).history(period="1d")['Close'].iloc[-1]
                        if price:
                            stock_value += (price * qty)
                    except Exception:
                        pass
            total_portfolio_value = cash_balance + stock_value
            if total_portfolio_value <= 0:
                total_portfolio_value = 100000.0

            # 4. Run Decision Logic
            params = {
                "sentiment_buy_threshold": settings.sentiment_buy_threshold,
                "max_position_weight": 0.30,      # 30% exposure cap per stock
                "cash_reserve_floor": 0.10,        # 10% cash reserve floor
                "base_allocation_pct": 0.10,       # 10% base allocation
                "min_trade_amount": settings.min_trade_amount,
                "stop_loss_pct": 0.05,             # 5% stop-loss
                "take_profit_pct": 0.15,           # 15% take-profit
            }

            decision = decide_trade(
                symbol=stock_symbol,
                position_qty=position_qty,
                avg_buy_price=avg_buy_price,
                current_price=current_price,
                sentiment_label=sentiment_label,
                hybrid_score=hybrid_score,
                prediction_direction=prediction_direction,
                cash_balance=cash_balance,
                total_portfolio_value=total_portfolio_value,
                params=params
            )

            if decision is None:
                logger.info("trade_no_action", stock=stock_symbol)
                return

            action = decision["action"]
            qty = decision["quantity"]
            reason = decision["reason"]

            if action == "BUY":
                allocation_amount = qty * current_price
                if cash_balance < allocation_amount:
                    logger.warning("insufficient_cash_buy", stock=stock_symbol, required=allocation_amount, cash=cash_balance)
                    return
                
                # A. Deduct Cash
                cur.execute("UPDATE portfolio SET quantity = quantity - %s, last_updated = NOW() WHERE symbol = 'USD'", (allocation_amount,))
                
                # B. Upsert Stock Position
                if position_qty > 0.0001:
                    new_qty = position_qty + qty
                    new_avg_price = ((position_qty * avg_buy_price) + (qty * current_price)) / new_qty
                    cur.execute("UPDATE portfolio SET quantity = %s, avg_price = %s, last_updated = NOW() WHERE symbol = %s", (new_qty, new_avg_price, stock_symbol))
                else:
                    cur.execute("INSERT INTO portfolio (asset_type, symbol, quantity, avg_price) VALUES ('STOCK', %s, %s, %s)", (stock_symbol, qty, current_price))
                
                # C. Log Trade
                cur.execute(
                    "INSERT INTO trade_logs (stock_symbol, action, quantity, price_at_trade, sentiment_score, prediction_score, reason) VALUES (%s, 'BUY', %s, %s, %s, %s, %s)",
                    (stock_symbol, qty, current_price, hybrid_score, prediction_confidence, reason)
                )
                logger.info("trade_executed_buy", stock=stock_symbol, qty=qty, price=current_price, reason=reason)

            elif action == "SELL":
                # Sell the entire position
                revenue = qty * current_price
                
                # A. Add Cash
                cur.execute("UPDATE portfolio SET quantity = quantity + %s, last_updated = NOW() WHERE symbol = 'USD'", (revenue,))
                
                # B. Remove Stock Position
                cur.execute("UPDATE portfolio SET quantity = 0, avg_price = 0, last_updated = NOW() WHERE symbol = %s", (stock_symbol,))
                
                # C. Log Trade
                cur.execute(
                    "INSERT INTO trade_logs (stock_symbol, action, quantity, price_at_trade, sentiment_score, prediction_score, reason) VALUES (%s, 'SELL', %s, %s, %s, %s, %s)",
                    (stock_symbol, qty, current_price, hybrid_score, 0.0, reason)
                )
                logger.info("trade_executed_sell", stock=stock_symbol, qty=qty, price=current_price, reason=reason)

            conn.commit()
            cur.close()

    except Exception as e:
        logger.error("trade_execution_failed", error=str(e), stock=stock_symbol)