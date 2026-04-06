import psycopg2
import os
from fastapi import APIRouter
from datetime import datetime
from dotenv import load_dotenv

from app.schemas.sentiment import SentimentResult, SentimentLabel, TimeWindow
from app.services.news import fetch_news_headlines
from app.services.sentiment_analyzer import calculate_sentiment

# Load env variables to get the DB connection string
load_dotenv()
DB_URL = os.getenv("DATABASE_URL")

router = APIRouter(prefix="/api/v1")

@router.post("/analyze", response_model=SentimentResult)
async def analyze_sentiment(stock_symbol: str):
    # 1. FETCH Data
    headlines = await fetch_news_headlines(stock_symbol, limit=10)
    
    # 2. ANALYZE Data
    analysis = calculate_sentiment(headlines)

    # 3. SAVE to Database (The New Step)
    try:
        if DB_URL:
            # Connect to Supabase
            conn = psycopg2.connect(DB_URL)
            cur = conn.cursor()
            
            # Raw SQL Query - using %s placeholders is CRITICAL for security
            insert_query = """
                INSERT INTO sentiment_results 
                (stock_symbol, sentiment_score, sentiment_label, confidence_score, time_window, source, generated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s);
            """
            
            # The data to fill into the %s slots
            data_to_insert = (
                stock_symbol,
                analysis["score"],
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
            conn.close()
            print(f" Saved sentiment for {stock_symbol} to DB")
        else:
            print("⚠️ DB_URL missing, skipping save.")
            
    except Exception as e:
        print(f" Database Error: {e}")

    # 4. RETURN Result
    return SentimentResult(
        stock_symbol=stock_symbol,
        sentiment_score=analysis["score"],
        sentiment_label=analysis["label"],
        confidence_score=analysis["confidence"],
        time_window=TimeWindow.hourly,
        source="news-api",
        generated_at=datetime.now()
    )