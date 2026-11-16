from datetime import datetime
import math

import yfinance as yf
from fastapi import APIRouter

from app.schemas.prediction import BacktestRequest, BacktestResult, BacktestResultV2, PredictionRequest, PredictionResult
from app.services.predictor import predict_next_day
from app.services.sentiment_analyzer import calculate_sentiment
from app.services.news import fetch_news_headlines
from app.services.backtest_engine import run_backtest_with_baselines
from fastapi import HTTPException

router = APIRouter(prefix="/api/v1")


@router.post("/predict", response_model=PredictionResult)
async def predict(request: PredictionRequest):
    headlines = await fetch_news_headlines(request.stock_symbol, limit=30)
    sentiment = calculate_sentiment(headlines)
    pred = predict_next_day(request.stock_symbol, request.lookback_days, sentiment["hybrid_score"])
    return PredictionResult(**pred)


@router.post("/backtest", response_model=BacktestResultV2)
async def backtest(request: BacktestRequest):
    symbol = request.stock_symbol.upper() if request.stock_symbol else "PORTFOLIO"
    try:
        params = {
            "initial_capital": 100000.0,
            "min_trade_amount": 10.0,
            "max_position_weight": 0.30 if symbol in ["PORTFOLIO", "ALL"] else 1.0,
            "cash_reserve_floor": 0.10 if symbol in ["PORTFOLIO", "ALL"] else 0.0,
            "base_allocation_pct": 0.10,
            "stop_loss_pct": 0.05,
            "take_profit_pct": 0.15,
            "transaction_cost_bps": 10.0
        }
        res = run_backtest_with_baselines(symbol, params)
        return BacktestResultV2(
            ticker=res["ticker"],
            trades_count=res["strategy"]["trades_count"],
            win_rate=res["strategy"]["win_rate"],
            sharpe_ratio=res["strategy"]["sharpe_ratio"],
            sortino_ratio=res["strategy"]["sortino_ratio"],
            total_return_pct=res["strategy"]["total_return_pct"],
            max_drawdown_pct=res["strategy"]["max_drawdown_pct"],
            benchmark_basket_return_pct=res["benchmark_basket"]["total_return_pct"],
            benchmark_spy_return_pct=res["benchmark_spy"]["total_return_pct"],
            alpha=res["strategy"]["total_return_pct"] - res["benchmark_basket"]["total_return_pct"],
            monte_carlo_sharpe_percentile=res["monte_carlo_sharpe_percentile"],
            curves=res["curves"],
            trades=res["trades"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

