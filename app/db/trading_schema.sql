
CREATE TABLE IF NOT EXISTS portfolio (
    id SERIAL PRIMARY KEY,
    asset_type VARCHAR(10) NOT NULL, -- 'CASH' or 'STOCK'
    symbol VARCHAR(10) NOT NULL,     -- 'USD' for cash, 'AAPL', etc.
    quantity FLOAT NOT NULL,         -- How many shares (or total dollars for cash)
    avg_price FLOAT DEFAULT 0.0,     -- Average buy price
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. The Journal: Tracks AI decisions (Transparency)
CREATE TABLE IF NOT EXISTS trade_logs (
    id SERIAL PRIMARY KEY,
    stock_symbol VARCHAR(10) NOT NULL,
    action VARCHAR(10) NOT NULL,     -- 'BUY' or 'SELL'
    quantity FLOAT NOT NULL,
    price_at_trade FLOAT NOT NULL,
    sentiment_score FLOAT NOT NULL,  -- The "Why"
    reason TEXT,                     -- Human readable explanation
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Seed Money: Give ourselves $100,000 fake dollars (Only run if table is empty)
INSERT INTO portfolio (asset_type, symbol, quantity, avg_price)
SELECT 'CASH', 'USD', 100000, 1.0
WHERE NOT EXISTS (SELECT 1 FROM portfolio WHERE symbol = 'USD');