from datetime import datetime
from pydantic import BaseModel, Field


class PredictionRequest(BaseModel):
    stock_symbol: str = Field(..., min_length=1)
    lookback_days: int = 180


class PredictionResult(BaseModel):
    stock_symbol: str
    predicted_direction: str
    predicted_return: float
    confidence: float
    hybrid_sentiment_score: float
    generated_at: datetime


class BacktestRequest(BaseModel):
    stock_symbol: str
    lookback_days: int = 365


class BacktestResult(BaseModel):
    stock_symbol: str
    trades: int
    win_rate: float
    sharpe_ratio: float
    strategy_return_pct: float
    benchmark_return_pct: float
    alpha: float


class BacktestResultV2(BaseModel):
    ticker: str
    trades_count: int
    win_rate: float
    sharpe_ratio: float
    sortino_ratio: float
    total_return_pct: float
    max_drawdown_pct: float
    benchmark_basket_return_pct: float
    benchmark_spy_return_pct: float
    alpha: float
    monte_carlo_sharpe_percentile: float
    curves: dict
    trades: list

