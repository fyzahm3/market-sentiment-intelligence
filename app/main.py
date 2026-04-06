from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.sentiment import router as sentiment_router
from app.api.v1.finance import router as finance_router
app=FastAPI(title="market-sentiment-intelligence")



app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sentiment_router)
app.include_router(finance_router)
@app.get("/")
def root():
    return {"message":"Market Sentiment Intelligence API v1 is running"}

