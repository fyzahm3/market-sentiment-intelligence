from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import yfinance as yf
from sklearn.preprocessing import StandardScaler

from app.core.cache import cache_get_json, cache_set_json
from app.core.config import settings


class DirectionLSTM(nn.Module):
    def __init__(self, input_size: int, hidden_size: int = 32) -> None:
        super().__init__()
        self.lstm = nn.LSTM(input_size=input_size, hidden_size=hidden_size, batch_first=True)
        self.fc = nn.Linear(hidden_size, 1)

    def forward(self, x):
        out, _ = self.lstm(x)
        out = out[:, -1, :]
        return torch.sigmoid(self.fc(out))


@dataclass
class PredictorArtifacts:
    model: DirectionLSTM
    scaler: StandardScaler
    feature_cols: list[str]


def _build_features(stock_symbol: str, lookback_days: int, hybrid_sentiment: float) -> pd.DataFrame:
    hist = yf.Ticker(stock_symbol).history(period=f"{lookback_days}d")
    if hist.empty:
        return pd.DataFrame()
    df = hist[["Close", "Volume"]].copy()
    df["return"] = df["Close"].pct_change()
    df["volatility"] = df["return"].rolling(5).std()
    df["hybrid_sentiment"] = hybrid_sentiment
    df["target"] = (df["return"].shift(-1) > 0).astype(float)
    return df.dropna()


def _make_sequences(values: np.ndarray, targets: np.ndarray, seq_len: int) -> Tuple[np.ndarray, np.ndarray]:
    xs, ys = [], []
    for i in range(seq_len, len(values)):
        xs.append(values[i - seq_len : i])
        ys.append(targets[i])
    return np.array(xs), np.array(ys)


def train_lightweight_model(stock_symbol: str, lookback_days: int, hybrid_sentiment: float) -> PredictorArtifacts | None:
    df = _build_features(stock_symbol, lookback_days, hybrid_sentiment)
    if df.empty:
        return None
    feature_cols = ["return", "volatility", "Volume", "hybrid_sentiment"]
    scaler = StandardScaler()
    x_scaled = scaler.fit_transform(df[feature_cols].values)
    y = df["target"].values
    x_seq, y_seq = _make_sequences(x_scaled, y, settings.lstm_sequence_length)
    if len(x_seq) < 20:
        return None

    model = DirectionLSTM(input_size=len(feature_cols), hidden_size=settings.lstm_hidden_size)
    criterion = nn.BCELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=settings.lstm_learning_rate)
    x_tensor = torch.tensor(x_seq, dtype=torch.float32)
    y_tensor = torch.tensor(y_seq, dtype=torch.float32).reshape(-1, 1)

    model.train()
    for _ in range(settings.lstm_epochs):
        optimizer.zero_grad()
        pred = model(x_tensor)
        loss = criterion(pred, y_tensor)
        loss.backward()
        optimizer.step()

    return PredictorArtifacts(model=model, scaler=scaler, feature_cols=feature_cols)


def predict_next_day(stock_symbol: str, lookback_days: int, hybrid_sentiment: float) -> Dict:
    cache_key = f"pred:{stock_symbol}:{lookback_days}:{round(hybrid_sentiment, 4)}"
    cached = cache_get_json(cache_key)
    if cached is not None:
        return cached

    artifacts = train_lightweight_model(stock_symbol, lookback_days, hybrid_sentiment)
    if artifacts is None:
        return {
            "stock_symbol": stock_symbol,
            "predicted_direction": "neutral",
            "predicted_return": 0.0,
            "confidence": 0.0,
            "hybrid_sentiment_score": hybrid_sentiment,
            "generated_at": datetime.utcnow().isoformat(),
        }

    df = _build_features(stock_symbol, lookback_days, hybrid_sentiment)
    latest = artifacts.scaler.transform(df[artifacts.feature_cols].values)
    seq = latest[-settings.lstm_sequence_length :]
    x = torch.tensor(seq[np.newaxis, :, :], dtype=torch.float32)

    artifacts.model.eval()
    with torch.no_grad():
        prob_up = float(artifacts.model(x).item())
    predicted_return = (prob_up - 0.5) * 0.04
    result = {
        "stock_symbol": stock_symbol,
        "predicted_direction": "up" if prob_up >= 0.5 else "down",
        "predicted_return": predicted_return,
        "confidence": abs(prob_up - 0.5) * 2,
        "hybrid_sentiment_score": hybrid_sentiment,
        "generated_at": datetime.utcnow().isoformat(),
    }
    cache_set_json(cache_key, result, settings.prediction_cache_ttl_seconds)
    return result
