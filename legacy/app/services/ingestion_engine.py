import asyncio
from datetime import datetime
import yfinance as yf

from app.core.config import settings
from app.core.logging import get_logger
from app.db.connection import get_db_connection
from app.db.init_db import init_db
from app.services.predictor import predict_next_day
from app.services.trader import execute_trade_logic
from app.services.news import fetch_news_headlines
from app.services.sentiment_analyzer import calculate_sentiment

logger = get_logger("services.ingestion")
TARGET_STOCKS = settings.target_stock_list

# --- HELPER: SNAPSHOT PERFORMANCE ---
def record_performance_snapshot(cur):
    """Calculates current value of AI vs Benchmark and saves history"""
    logger.info("snapshot_start")
    
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
    
    logger.info("snapshot_saved", ai_value=total_ai, benchmark_value=total_bench, alpha=alpha)

# --- MAIN ENGINE ---
async def process_stock(stock: str, cur):
    logger.info("stock_processing", stock=stock)
    try:
        headlines = await fetch_news_headlines(stock, limit=50)
        if not headlines:
            return

        analysis = calculate_sentiment(headlines)
        prediction = predict_next_day(stock, lookback_days=180, hybrid_sentiment=analysis["hybrid_score"])

        # Save Sentiment
        cur.execute("""
            INSERT INTO sentiment_results 
            (stock_symbol, sentiment_score, vader_score, finbert_score, hybrid_score, sentiment_label, confidence_score, time_window, source, generated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """, (
            stock,
            analysis["score"],
            analysis["vader_score"],
            analysis["finbert_score"],
            analysis["hybrid_score"],
            analysis["label"],
            analysis["confidence"],
            "batch_hourly",
            "news-api",
            datetime.now(),
        ))
        
        # Execute Trade
        execute_trade_logic(
            stock,
            analysis["hybrid_score"],
            analysis["label"],
            analysis["confidence"],
            prediction["confidence"],
            prediction["predicted_direction"],
        )
        
    except Exception as e:
        logger.error("stock_process_error", stock=stock, error=str(e))

async def run_continuous_job():
    init_db()
    logger.info("engine_started", started_at=str(datetime.utcnow()))
    
    while True:
        try:
            with get_db_connection() as conn:
                conn.autocommit = True
                cur = conn.cursor()

                logger.info("batch_scan_started", at=datetime.now().strftime("%H:%M:%S"))
            
                # 1. Process All Stocks
                for stock in TARGET_STOCKS:
                    await process_stock(stock, cur)
                    await asyncio.sleep(1)

                # 2. Record History
                record_performance_snapshot(cur)

                cur.close()
            
            await asyncio.sleep(settings.scan_interval_seconds)

        except Exception as e:
            logger.error("engine_failure", error=str(e))
            await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(run_continuous_job())