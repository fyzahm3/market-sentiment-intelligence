from fastapi import APIRouter
from datetime import datetime
from app.schemas.sentiment import SentimentResult, SentimentLabel, TimeWindow

from app.services.news import fetch_news_headlines
from app.services.sentiment_analyzer import calculate_sentiment # <--- NEW

router = APIRouter(prefix="/api/v1")

@router.post("/analyze", response_model=SentimentResult)
async def analyze_sentiment(stock_symbol: str):

    headlines = await fetch_news_headlines(stock_symbol, limit=10)
    

    analysis = calculate_sentiment(headlines)

    return SentimentResult(
        stock_symbol=stock_symbol,
        sentiment_score=analysis["score"],
        sentiment_label=analysis["label"],
        confidence_score=analysis["confidence"],
        time_window=TimeWindow.hourly,
        source="news-api",
        generated_at=datetime.now()
    )