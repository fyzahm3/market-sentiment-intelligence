from fastapi import APIRouter
from datetime import datetime
from app.schemas.sentiment import SentimentResult, SentimentLabel, TimeWindow

router=APIRouter(prefix="/api/v1")

@router.get("/sentiment", response_model=SentimentResult)
def get_sentiment():
    return SentimentResult(
        stock_symbol="AAPL",
        sentiment_score=0.85,
        sentiment_label=SentimentLabel.bullish,
        confidence_score=0.92,
        time_window=TimeWindow.hourly,
        source="reddit",
        generated_at=datetime.now()
    )