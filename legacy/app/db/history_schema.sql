CREATE TABLE IF NOT EXISTS performance_history (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ai_fund_value FLOAT NOT NULL,
    benchmark_value FLOAT NOT NULL,
    alpha FLOAT NOT NULL
);