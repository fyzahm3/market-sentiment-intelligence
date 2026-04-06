import yfinance as yf
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.getenv("DATABASE_URL")

# CONFIGURATION
MAX_POSITION_SIZE = 20000  # Maximum investment per stock
# We lowered the threshold so we don't skip trades easily, 
# but the Formula will naturally buy less if confidence is low.
MIN_CONFIDENCE_THRESHOLD = 0.10 

def execute_trade_logic(stock_symbol, sentiment_score, sentiment_label, confidence_score):
    """
    Smart Index Strategy:
    - Avoid Bearish stocks.
    - Buy Neutral (Small allocation).
    - Buy Bullish (Large allocation).
    """
    
    # --- DEBUG PRINT ---
    print(f"      🔍 Checking Logic for {stock_symbol}: Label='{sentiment_label}', Score={sentiment_score:.2f}")
    
    # RULE 1: STRICTLY AVOID BEARISH
    if sentiment_label.lower() == "bearish":
        print(f"      ✋ Skipping {stock_symbol}: Bearish Outlook (Protecting Capital)")
        return

    # RULE 2: MATH SAFETY
    # If the score is 0 or negative (even if labeled Neutral), we can't use the formula.
    if sentiment_score <= 0:
        print(f"      ✋ Skipping {stock_symbol}: Score is {sentiment_score} (Need positive score to buy)")
        return

    # RULE 3: DYNAMIC SIZING FORMULA
    # This fulfills your requirement: "invest in accordance to confidence and score"
    # - Neutral (e.g., Score 0.05): $20,000 * 0.05 * 0.9 = $900 (Small Buy)
    # - Bullish (e.g., Score 0.50): $20,000 * 0.50 * 0.9 = $9,000 (Big Buy)
    allocation_amount = MAX_POSITION_SIZE * sentiment_score * confidence_score
    
    # Cap the allocation if it somehow exceeds max (sanity check)
    if allocation_amount > MAX_POSITION_SIZE:
        allocation_amount = MAX_POSITION_SIZE

    # Connect to Bank (DB)
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()

        # 1. Check Cash Balance
        cur.execute("SELECT quantity FROM portfolio WHERE symbol = 'USD'")
        row = cur.fetchone()
        cash_balance = row[0] if row else 0.0

        if cash_balance < allocation_amount:
            print(f"      ⚠️ Not enough cash! (Need ${allocation_amount:.2f}, Have ${cash_balance:.2f})")
            allocation_amount = cash_balance # Adjust to use remaining cash

        if allocation_amount < 10: # Lowered limit to allow small "Neutral" buys
            print(f"      ⚠️ Allocation ${allocation_amount:.2f} too small, skipping.")
            conn.close()
            return

        # 2. Get Real-Time Stock Price
        try:
            ticker = yf.Ticker(stock_symbol)
            current_price = ticker.fast_info.last_price
            if current_price is None:
                # Fallback
                hist = ticker.history(period="1d")
                if not hist.empty:
                    current_price = hist['Close'].iloc[-1]
        except Exception as e:
            print(f"      ❌ Price Error: {e}")
            conn.close()
            return

        if not current_price:
             conn.close()
             return

        # 3. Calculate Quantity
        quantity_to_buy = allocation_amount / current_price

        # 4. EXECUTE TRADE
        # A. Deduct Cash
        cur.execute("""
            UPDATE portfolio 
            SET quantity = quantity - %s, last_updated = NOW() 
            WHERE symbol = 'USD'
        """, (allocation_amount,))

        # B. Upsert Stock
        cur.execute("SELECT quantity, avg_price FROM portfolio WHERE symbol = %s", (stock_symbol,))
        existing_stock = cur.fetchone()
        
        if existing_stock:
            old_qty, old_price = existing_stock
            new_qty = old_qty + quantity_to_buy
            new_avg_price = ((old_qty * old_price) + (quantity_to_buy * current_price)) / new_qty
            
            cur.execute("""
                UPDATE portfolio SET quantity = %s, avg_price = %s, last_updated = NOW()
                WHERE symbol = %s
            """, (new_qty, new_avg_price, stock_symbol))
        else:
            cur.execute("""
                INSERT INTO portfolio (asset_type, symbol, quantity, avg_price)
                VALUES ('STOCK', %s, %s, %s)
            """, (stock_symbol, quantity_to_buy, current_price))

        # C. Log Trade
        log_query = """
            INSERT INTO trade_logs (stock_symbol, action, quantity, price_at_trade, sentiment_score, reason)
            VALUES (%s, 'BUY', %s, %s, %s, %s)
        """
        reason_text = f"Smart Allocation: Sent {sentiment_score:.2f} * Conf {confidence_score:.2f}"
        cur.execute(log_query, (stock_symbol, quantity_to_buy, current_price, sentiment_score, reason_text))

        conn.commit()
        cur.close()
        conn.close()
        
        print(f"      💸 BOUGHT {quantity_to_buy:.4f} shares of {stock_symbol}")
        print(f"         Spent: ${allocation_amount:.2f} (Sentiment: {sentiment_score:.2f})")

    except Exception as e:
        print(f"      ❌ Trade execution failed: {e}")