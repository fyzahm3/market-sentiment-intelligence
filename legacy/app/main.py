from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.sentiment import router as sentiment_router
from app.api.v1.finance import router as finance_router
from app.api.v1.prediction import router as prediction_router
from app.api.v1.auth import router as auth_router
from app.api.v1.health import router as health_router
from app.api.v1.memo import router as memo_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.rate_limit import limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi import _rate_limit_exceeded_handler

configure_logging()
app=FastAPI(title=settings.app_name)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)



app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sentiment_router)
app.include_router(finance_router)
app.include_router(prediction_router)
app.include_router(auth_router)
app.include_router(health_router)
app.include_router(memo_router)

@app.get("/")
def root():
    return {"message":"Market Sentiment Intelligence API v1 is running"}


