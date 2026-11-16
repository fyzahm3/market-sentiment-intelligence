import json
import google.generativeai as genai
from typing import List, Dict
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("services.sentiment_llm")

# Configure Gemini
if settings.gemini_api_key and settings.gemini_api_key != "change-me":
    genai.configure(api_key=settings.gemini_api_key)
    _has_gemini = True
else:
    logger.warning("gemini_key_not_configured_using_mock_sentiment")
    _has_gemini = False

def classify_headlines_llm(headlines: List[str]) -> List[Dict]:
    """
    Classifies a list of headlines using Gemini 1.5 Flash in batch.
    Returns a list of dicts: [{"sentiment": "positive"|"negative"|"neutral", "confidence": float}]
    """
    if not headlines:
        return []

    if not _has_gemini:
        # Mock sentiment fallback: label based on keywords
        results = []
        for h in headlines:
            hl = h.lower()
            if any(w in hl for w in ["drop", "fall", "miss", "bearish", "down", "lower", "loss", "decline"]):
                results.append({"sentiment": "negative", "confidence": 0.70})
            elif any(w in hl for w in ["rise", "gain", "beat", "bullish", "up", "higher", "profit", "growth"]):
                results.append({"sentiment": "positive", "confidence": 0.70})
            else:
                results.append({"sentiment": "neutral", "confidence": 0.60})
        return results

    try:
        # Batch headlines together into a prompt
        headlines_list = "\n".join([f"{i+1}. {text}" for i, text in enumerate(headlines)])
        
        prompt = f"""
You are an expert financial analyst. Your task is to classify the sentiment of financial news headlines into one of three classes: positive, negative, or neutral.

You MUST respond with a valid JSON array of objects, where each object corresponds to a headline and contains exactly two keys:
- "sentiment": must be one of "positive", "negative", or "neutral"
- "confidence": must be a float between 0.0 and 1.0 representing your confidence.

Example output:
[
  {{"sentiment": "negative", "confidence": 0.95}},
  {{"sentiment": "positive", "confidence": 0.98}}
]

Here is the numbered list of headlines to classify:
{headlines_list}

Return the JSON array representing the classifications in the exact order of the inputs:
"""
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.0
            )
        )
        
        text = response.text.strip()
        data = json.loads(text)
        
        if isinstance(data, list) and len(data) == len(headlines):
            # Validate output structure
            validated = []
            for item in data:
                sent = item.get("sentiment", "neutral").lower()
                if sent not in ["positive", "negative", "neutral"]:
                    sent = "neutral"
                conf = float(item.get("confidence", 0.50))
                validated.append({"sentiment": sent, "confidence": conf})
            return validated
        else:
            logger.error("invalid_llm_response_format", length_mismatch=True)
            raise ValueError("Response length mismatch")

    except Exception as e:
        logger.error("llm_sentiment_classification_failed", error=str(e))
        # Fallback to neutral
        return [{"sentiment": "neutral", "confidence": 0.50} for _ in headlines]
