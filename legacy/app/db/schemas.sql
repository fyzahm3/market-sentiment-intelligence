CREATE TABLE IF NOT EXISTS sentiment_results (
    id SERIAL PRIMARY KEY,                  
    stock_symbol VARCHAR(20) NOT NULL,      
    sentiment_score FLOAT NOT NULL,         
    vader_score FLOAT NOT NULL DEFAULT 0,
    finbert_score FLOAT NOT NULL DEFAULT 0,
    hybrid_score FLOAT NOT NULL DEFAULT 0,
    sentiment_label VARCHAR(20) NOT NULL,   
    confidence_score FLOAT NOT NULL,        
    time_window VARCHAR(20) NOT NULL,      
    source VARCHAR(50) NOT NULL,            
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP 
);


CREATE INDEX IF NOT EXISTS idx_stock_symbol ON sentiment_results(stock_symbol);