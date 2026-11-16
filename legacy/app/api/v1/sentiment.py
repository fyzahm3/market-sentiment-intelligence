from fastapi import APIRouter
from datetime import datetime

from app.core.config import settings
from app.core.logging import get_logger
from app.db.connection import get_db_connection
from app.schemas.sentiment import SentimentResult, TimeWindow
from app.services.news import fetch_news_headlines
from app.services.sentiment_analyzer import calculate_sentiment

logger = get_logger("api.sentiment")

router = APIRouter(prefix="/api/v1")

@router.post("/analyze", response_model=SentimentResult)
async def analyze_sentiment(stock_symbol: str):
    # 1. FETCH Data
    headlines = await fetch_news_headlines(stock_symbol, limit=10)
    
    # 2. ANALYZE Data
    analysis = calculate_sentiment(headlines)

    # 3. SAVE to Database (The New Step)
    try:
        if settings.database_url:
            with get_db_connection() as conn:
                cur = conn.cursor()
            
                # Raw SQL Query - using %s placeholders is CRITICAL for security
                insert_query = """
                    INSERT INTO sentiment_results 
                    (stock_symbol, sentiment_score, vader_score, finbert_score, hybrid_score, sentiment_label, confidence_score, time_window, source, generated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """
            
                # The data to fill into the %s slots
                data_to_insert = (
                    stock_symbol,
                    analysis["score"],
                    analysis["vader_score"],
                    analysis["finbert_score"],
                    analysis["hybrid_score"],
                    analysis["label"],
                    analysis["confidence"],
                    "hourly",
                    "news-api",
                    datetime.now()
                )
            
                # Execute and Save
                cur.execute(insert_query, data_to_insert)
                conn.commit()
            
                # Clean up
                cur.close()
                logger.info("sentiment_saved", stock=stock_symbol)
        else:
            logger.warning("db_url_missing")
            
    except Exception as e:
        logger.error("sentiment_db_error", error=str(e))

    # 4. RETURN Result
    return SentimentResult(
        stock_symbol=stock_symbol,
        sentiment_score=analysis["score"],
        vader_score=analysis["vader_score"],
        finbert_score=analysis["finbert_score"],
        hybrid_score=analysis["hybrid_score"],
        sentiment_label=analysis["label"],
        confidence_score=analysis["confidence"],
        time_window=TimeWindow.hourly,
        source="news-api",
        generated_at=datetime.now()
    )