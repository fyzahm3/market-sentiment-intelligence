import asyncio
import psycopg2
import time
import os
from datetime import datetime
import yfinance as yf
from dotenv import load_dotenv

from app.services.trader import execute_trade_logic
from app.services.news import fetch_news_headlines
from app.services.sentiment_analyzer import calculate_sentiment

load_dotenv()
DB_URL = os.getenv("DATABASE_URL")
TARGET_STOCKS = ["AAPL", "TSLA", "GOOGL", "AMZN", "MSFT", "NVDA", "META", "NFLX"]

# --- HELPER: SNAPSHOT PERFORMANCE ---
def record_performance_snapshot(cur):
    """Calculates current value of AI vs Benchmark and saves history"""
    print("      📸 Taking Performance Snapshot...")
    
    # 1. Calculate AI Value
    cur.execute("SELECT quantity FROM portfolio WHERE symbol = 'USD'")
    cash = cur.fetchone()[0]
    
    cur.execute("SELECT symbol, quantity FROM portfolio WHERE asset_type = 'STOCK'")
    ai_holdings = cur.fetchall()
    
    ai_stock_val = 0
    live_prices = {}
    
    for sym, qty in ai_holdings:
        if qty > 0:
            price = yf.Ticker(sym).fast_info.last_price
            if price:
                live_prices[sym] = price
                ai_stock_val += (price * qty)
    
    total_ai = cash + ai_stock_val

    # 2. Calculate Benchmark Value
    cur.execute("SELECT symbol, initial_shares FROM benchmark_portfolio")
    bench_holdings = cur.fetchall()
    
    total_bench = 0
    for sym, shares in bench_holdings:
        price = live_prices.get(sym)
        if not price:
            price = yf.Ticker(sym).fast_info.last_price
            live_prices[sym] = price
        if price:
            total_bench += (price * shares)

    # 3. Calculate Alpha
    start_cap = 100000
    ai_pct = ((total_ai - start_cap) / start_cap) * 100
    bench_pct = ((total_bench - start_cap) / start_cap) * 100
    alpha = ai_pct - bench_pct

    # 4. Save to History
    cur.execute("""
        INSERT INTO performance_history (ai_fund_value, benchmark_value, alpha)
        VALUES (%s, %s, %s)
    """, (total_ai, total_bench, alpha))
    
    print(f"      ✅ Snapshot Saved: AI ${total_ai:.0f} vs Index ${total_bench:.0f} (Alpha: {alpha:.2f}%)")

# --- MAIN ENGINE ---
async def process_stock(stock: str, cur):
    print(f"   Analyzing {stock}...")
    try:
        headlines = await fetch_news_headlines(stock, limit=50)
        if not headlines: return

        analysis = calculate_sentiment(headlines)

        # Save Sentiment
        cur.execute("""
            INSERT INTO sentiment_results 
            (stock_symbol, sentiment_score, sentiment_label, confidence_score, time_window, source, generated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s);
        """, (stock, analysis["score"], analysis["label"], analysis["confidence"], "batch_hourly", "news-api", datetime.now()))
        
        # Execute Trade
        execute_trade_logic(stock, analysis["score"], analysis["label"], analysis["confidence"])
        
    except Exception as e:
        print(f"   ❌ Error {stock}: {e}")

async def run_continuous_job():
    print(f"🚀 AI Fund Engine Started at {datetime.now()}")
    
    while True:
        try:
            conn = psycopg2.connect(DB_URL)
            conn.autocommit = True # Auto commit transactions
            cur = conn.cursor()

            print(f"\n⏰ Starting Batch Scan: {datetime.now().strftime('%H:%M:%S')}")
            
            # 1. Process All Stocks
            for stock in TARGET_STOCKS:
                await process_stock(stock, cur)
                await asyncio.sleep(1) # Short pause between API calls

            # 2. Record History
            record_performance_snapshot(cur)

            cur.close()
            conn.close()
            
            # 3. Wait for next cycle
            # For DEMO purposes, I set this to 60 seconds. 
            # Change to 3600 for real 1-hour loops.
            WAIT_SECONDS = 60 
            print(f"💤 Sleeping for {WAIT_SECONDS}s...")
            await asyncio.sleep(WAIT_SECONDS)

        except Exception as e:
            print(f"❌ CRITICAL ENGINE FAILURE: {e}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(run_continuous_job())