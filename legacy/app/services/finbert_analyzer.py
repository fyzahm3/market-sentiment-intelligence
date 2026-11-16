from typing import List

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from app.core.logging import get_logger

logger = get_logger("services.finbert")
_tokenizer = None
_model = None
_labels = ["negative", "neutral", "positive"]


def _load_model() -> None:
    global _tokenizer, _model
    if _tokenizer is not None and _model is not None:
        return
    logger.info("loading_finbert_model", model="ProsusAI/finbert")
    _tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
    _model = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert")
    _model.eval()


def score_headlines(headlines: List[str]) -> float:
    if not headlines:
        return 0.0
    _load_model()
    encoded = _tokenizer(headlines, return_tensors="pt", truncation=True, padding=True, max_length=128)
    with torch.no_grad():
        outputs = _model(**encoded)
        probs = torch.softmax(outputs.logits, dim=-1)
    sentiment_values = torch.tensor([1.0, -1.0, 0.0])
    weighted = torch.matmul(probs, sentiment_values)
    return float(weighted.mean().item())

