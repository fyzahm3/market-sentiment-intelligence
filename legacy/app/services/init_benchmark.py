import yfinance as yf
from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger
from app.db.connection import get_db_connection
from app.db.init_db import init_db

logger = get_logger("services.benchmark")
TARGET_STOCKS = settings.target_stock_list
INITIAL_CAPITAL = settings.initial_capital

def init_benchmark():
    init_db()
    with get_db_connection() as conn:
        cur = conn.cursor()
    
        # 1. Create Table
        schema_path = Path(__file__).resolve().parents[1] / "db" / "benchmark_schema.sql"
        cur.execute(schema_path.read_text(encoding="utf-8"))
    
        # 2. Check if already initialized
        cur.execute("SELECT count(*) FROM benchmark_portfolio")
        if cur.fetchone()[0] > 0:
            logger.info("benchmark_exists_skip")
            return

        logger.info("benchmark_init_start", capital=INITIAL_CAPITAL)
    
        allocation_per_stock = INITIAL_CAPITAL / len(TARGET_STOCKS)
    
        for stock in TARGET_STOCKS:
            try:
                ticker = yf.Ticker(stock)
                price = ticker.fast_info.last_price
            
                if price:
                    shares = allocation_per_stock / price
                    cur.execute("""
                        INSERT INTO benchmark_portfolio (symbol, initial_shares, initial_price)
                        VALUES (%s, %s, %s)
                    """, (stock, shares, price))
                    logger.info("benchmark_seeded_stock", stock=stock, shares=shares, price=price)
            except Exception as e:
                logger.error("benchmark_seed_error", stock=stock, error=str(e))

        conn.commit()
        cur.close()
    logger.info("benchmark_initialized")

if __name__ == "__main__":
    init_benchmark()