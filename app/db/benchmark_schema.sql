CREATE TABLE IF NOT EXISTS benchmark_portfolio (
    symbol VARCHAR(10) PRIMARY KEY,
    initial_shares FLOAT NOT NULL,
    initial_price FLOAT NOT NULL,
    locked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);