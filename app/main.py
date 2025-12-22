from fastapi import FastAPI
from app.api.v1.sentiment import router as sentiment_router

app=FastAPI(title="market-sentiment-intelligence")

app.include_router(sentiment_router)

@app.get("/")
def root():
    return {"message":"Market Sentiment Intelligence API v1 is running"}