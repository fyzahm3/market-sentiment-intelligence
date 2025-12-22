from enum import Enum
from datetime import datetime
from pydantic import BaseModel
class SentimentLabel(str,Enum):
    bullish="bullish"
    neutral="neutral"
    bearish="bearish"

class TimeWindow(str,Enum):
    hourly="hourly"

class SentimentResult(BaseModel):
    stock_symbol: str
    sentiment_score: float
    sentiment_label: SentimentLabel
    confidence_score: float
    time_window: TimeWindow
    source: str
    generated_at: datetime

