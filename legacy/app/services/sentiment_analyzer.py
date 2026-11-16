import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer

from app.core.cache import cache_get_json, cache_set_json
from app.core.config import settings
from app.services.finbert_analyzer import score_headlines

try:
    nltk.data.find('sentiment/vader_lexicon.zip')
except LookupError:
    nltk.download('vader_lexicon')

analyzer = SentimentIntensityAnalyzer()


def _cache_key(text_list: list[str]) -> str:
    return f"sentiment:{'|'.join(text_list)}"

def calculate_sentiment(text_list: list[str]) -> dict:
    if not text_list:
        return {
            "score": 0.0,
            "vader_score": 0.0,
            "finbert_score": 0.0,
            "hybrid_score": 0.0,
            "label": "neutral",
            "confidence": 0.0,
        }

    cache_key = _cache_key(text_list)
    cached = cache_get_json(cache_key)
    if cached is not None:
        return cached

    total_compound_score = 0
    count = 0

    for text in text_list:
        
        scores = analyzer.polarity_scores(text)
        total_compound_score += scores['compound']
        count += 1


    vader_score = total_compound_score / count
    finbert_score = score_headlines(text_list)
    hybrid_score = (
        settings.sentiment_vader_weight * vader_score
        + settings.sentiment_finbert_weight * finbert_score
    )

    if hybrid_score >= settings.sentiment_neutral_band:
        label = "bullish"
    elif hybrid_score <= -settings.sentiment_neutral_band:
        label = "bearish"
    else:
        label = "neutral"


    confidence = min(1.0, abs(hybrid_score))

    result = {
        "score": hybrid_score,
        "vader_score": vader_score,
        "finbert_score": finbert_score,
        "hybrid_score": hybrid_score,
        "label": label,
        "confidence": confidence
    }
    cache_set_json(cache_key, result, settings.sentiment_cache_ttl_seconds)
    return result