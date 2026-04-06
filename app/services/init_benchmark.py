import yfinance as yf
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.getenv("DATABASE_URL")
TARGET_STOCKS = ["AAPL", "TSLA", "GOOGL", "AMZN", "MSFT", "NVDA", "META", "NFLX"]
INITIAL_CAPITAL = 100000

def init_benchmark():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    # 1. Create Table
    with open("app/db/benchmark_schema.sql", "r") as f:
        cur.execute(f.read())
    
    # 2. Check if already initialized
    cur.execute("SELECT count(*) FROM benchmark_portfolio")
    if cur.fetchone()[0] > 0:
        print("Benchmark already exists. Skipping initialization.")
        return

    print("🚀 Initializing Equal-Weight Index Fund ($100k)...")
    
    allocation_per_stock = INITIAL_CAPITAL / len(TARGET_STOCKS) # $12,500 each
    
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
                print(f"   Index bought {shares:.2f} shares of {stock} @ ${price:.2f}")
        except Exception as e:
            print(f"   Error fetching {stock}: {e}")

    conn.commit()
    cur.close()
    conn.close()
    print("Benchmark Portfolio Locked In.")

if __name__ == "__main__":
    init_benchmark()