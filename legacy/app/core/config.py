from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "market-sentiment-intelligence"
    app_env: str = "dev"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    database_url: str = Field(..., alias="DATABASE_URL")
    redis_url: str = Field("redis://localhost:6379/0", alias="REDIS_URL")
    news_api_key: str = Field(..., alias="NEWS_API_KEY")
    gemini_api_key: str = Field("change-me", alias="GEMINI_API_KEY")

    cors_origins: str = Field("http://localhost:5173", alias="CORS_ORIGINS")
    requests_per_minute: int = Field(120, alias="REQUESTS_PER_MINUTE")
    jwt_secret_key: str = Field("change-me", alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field("HS256", alias="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(120, alias="JWT_EXPIRE_MINUTES")

    sentiment_vader_weight: float = Field(0.4, alias="SENTIMENT_VADER_WEIGHT")
    sentiment_finbert_weight: float = Field(0.6, alias="SENTIMENT_FINBERT_WEIGHT")
    sentiment_buy_threshold: float = Field(0.10, alias="SENTIMENT_BUY_THRESHOLD")
    sentiment_neutral_band: float = Field(0.05, alias="SENTIMENT_NEUTRAL_BAND")

    news_cache_ttl_seconds: int = Field(600, alias="NEWS_CACHE_TTL_SECONDS")
    sentiment_cache_ttl_seconds: int = Field(1800, alias="SENTIMENT_CACHE_TTL_SECONDS")
    prediction_cache_ttl_seconds: int = Field(1800, alias="PREDICTION_CACHE_TTL_SECONDS")

    target_stocks: str = Field(
        "AAPL,TSLA,GOOGL,AMZN,MSFT,NVDA,META,NFLX", alias="TARGET_STOCKS"
    )
    initial_capital: float = Field(100000, alias="INITIAL_CAPITAL")
    max_position_size: float = Field(20000, alias="MAX_POSITION_SIZE")
    min_trade_amount: float = Field(10, alias="MIN_TRADE_AMOUNT")
    scan_interval_seconds: int = Field(60, alias="SCAN_INTERVAL_SECONDS")

    model_dir: str = Field("artifacts/models", alias="MODEL_DIR")
    lstm_sequence_length: int = Field(45, alias="LSTM_SEQUENCE_LENGTH")
    lstm_hidden_size: int = Field(32, alias="LSTM_HIDDEN_SIZE")
    lstm_epochs: int = Field(10, alias="LSTM_EPOCHS")
    lstm_learning_rate: float = Field(0.001, alias="LSTM_LEARNING_RATE")
    lstm_batch_size: int = Field(16, alias="LSTM_BATCH_SIZE")

    @property
    def cors_origin_list(self) -> List[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def target_stock_list(self) -> List[str]:
        return [item.strip().upper() for item in self.target_stocks.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()