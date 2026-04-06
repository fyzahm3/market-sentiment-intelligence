import psycopg2
import os
import yfinance as yf
from fastapi import APIRouter
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.getenv("DATABASE_URL")

router = APIRouter(prefix="/api/v1")

@router.get("/portfolio")
def get_portfolio():
    """Returns all current holdings (Cash + Stocks)"""
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # Get everything we own
        query = "SELECT symbol, quantity, avg_price, asset_type FROM portfolio WHERE quantity > 0.0001 ORDER BY asset_type ASC, symbol ASC"
        cur.execute(query)
        rows = cur.fetchall()
        
        # Convert tuple rows to Clean JSON
        portfolio_data = []
        for row in rows:
            portfolio_data.append({
                "symbol": row[0],
                "quantity": row[1],
                "avg_price": row[2],
                "asset_type": row[3],
                # Estimate current value (simple calculation)
                "value": row[1] * row[2] 
            })
            
        cur.close()
        conn.close()
        return {"portfolio": portfolio_data}
        
    except Exception as e:
        return {"error": str(e)}

@router.get("/trades")
def get_trade_history():
    """Returns the last 50 decisions the AI made"""
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        query = """
            SELECT stock_symbol, action, quantity, price_at_trade, sentiment_score, reason, timestamp 
            FROM trade_logs 
            ORDER BY timestamp DESC 
            LIMIT 50
        """
        cur.execute(query)
        rows = cur.fetchall()
        
        history = []
        for row in rows:
            history.append({
                "symbol": row[0],
                "action": row[1],
                "quantity": row[2],
                "price": row[3],
                "score": row[4],
                "reason": row[5],
                "date": row[6]
            })
            
        cur.close()
        conn.close()
        return {"trades": history}
        
    except Exception as e:
        return {"error": str(e)}


@router.get("/performance")
def get_performance_metrics():
    """Compares AI Fund vs. Passive Index Fund"""
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # 1. Calculate AI Portfolio Value (Real Money)
        # Cash
        cur.execute("SELECT quantity FROM portfolio WHERE symbol = 'USD'")
        cash_row = cur.fetchone()
        ai_cash = cash_row[0] if cash_row else 0.0
        
        # Stocks
        cur.execute("SELECT symbol, quantity FROM portfolio WHERE asset_type = 'STOCK'")
        ai_holdings = cur.fetchall()
        
        ai_stock_value = 0.0
        live_prices = {} # Cache prices so we don't fetch twice
        
        for symbol, qty in ai_holdings:
            if qty > 0:
                ticker = yf.Ticker(symbol)
                price = ticker.fast_info.last_price
                if price:
                    live_prices[symbol] = price
                    ai_stock_value += (price * qty)
        
        total_ai_value = ai_cash + ai_stock_value

        # 2. Calculate Benchmark Value (Ghost Money)
        # We assume Benchmark is 100% invested (No cash)
        cur.execute("SELECT symbol, initial_shares FROM benchmark_portfolio")
        benchmark_holdings = cur.fetchall()
        
        total_benchmark_value = 0.0
        
        for symbol, shares in benchmark_holdings:
            # Use cached price if available, else fetch
            price = live_prices.get(symbol)
            if not price:
                price = yf.Ticker(symbol).fast_info.last_price
                live_prices[symbol] = price
            
            if price:
                total_benchmark_value += (price * shares)

        # 3. Calculate Metrics
        start_capital = 100000
        ai_return_pct = ((total_ai_value - start_capital) / start_capital) * 100
        benchmark_return_pct = ((total_benchmark_value - start_capital) / start_capital) * 100
        
        # Alpha = AI Performance - Benchmark Performance
        alpha = ai_return_pct - benchmark_return_pct

        cur.close()
        conn.close()
        
        return {
            "ai_fund": {
                "value": total_ai_value,
                "return_pct": ai_return_pct
            },
            "benchmark_index": {
                "value": total_benchmark_value,
                "return_pct": benchmark_return_pct
            },
            "alpha": alpha, # Positive means you are beating the market
            "is_beating_market": alpha > 0
        }
        
    except Exception as e:
        return {"error": str(e)}
    
@router.get("/history")
def get_performance_history():
    """Returns the time-series data for the chart"""
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # Get last 24 records (assuming hourly runs = 24 hours)
        cur.execute("""
            SELECT timestamp, ai_fund_value, benchmark_value 
            FROM performance_history 
            ORDER BY timestamp ASC 
            LIMIT 100
        """)
        rows = cur.fetchall()
        
        chart_data = []
        for row in rows:
            chart_data.append({
                "time": row[0].strftime("%H:%M"), # Format time nicely
                "AI Fund": row[1],
                "S&P 500": row[2]
            })
            
        cur.close()
        conn.close()
        return {"history": chart_data}
    except Exception as e:
        return {"error": str(e)}