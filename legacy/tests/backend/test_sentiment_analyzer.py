from app.services.sentiment_analyzer import calculate_sentiment


def test_empty_sentiment_payload():
    result = calculate_sentiment([])
    assert result["label"] == "neutral"
    assert result["hybrid_score"] == 0.0
