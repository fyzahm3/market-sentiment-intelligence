import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer

try:
    nltk.data.find('sentiment/vader_lexicon.zip')
except LookupError:
    nltk.download('vader_lexicon')

analyzer = SentimentIntensityAnalyzer()

def calculate_sentiment(text_list: list[str]) -> dict:
    if not text_list:
        return {"score": 0, "label": "neutral", "confidence": 0}

    total_compound_score = 0
    count = 0

    for text in text_list:
        
        scores = analyzer.polarity_scores(text)
        total_compound_score += scores['compound']
        count += 1


    avg_score = total_compound_score / count
    

    if avg_score >= 0.05:
        label = "bullish"
    elif avg_score <= -0.05:
        label = "bearish"
    else:
        label = "neutral"


    confidence = abs(avg_score)

    return {
        "score": avg_score,
        "label": label,
        "confidence": confidence
    }