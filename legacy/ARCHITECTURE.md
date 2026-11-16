# Architecture

## System Diagram
```mermaid
flowchart LR
subgraph frontend [Frontend]
tabs[TabsUI]
client[ApiClientPolling]
end

subgraph backend [FastAPIBackend]
sent[SentimentAPI]
pred[PredictionAPI]
fin[FinanceAPI]
engine[IngestionEngine]
end

subgraph services [CoreServices]
news[NewsService]
hybrid[HybridSentiment]
lstm[LSTMPredictor]
trader[Trader]
end

subgraph infra [Infra]
pg[(PostgreSQL)]
redis[(Redis)]
newsapi[NewsAPI]
yf[YFinance]
finbert[FinBERTModel]
end

tabs --> client
client --> sent
client --> pred
client --> fin
engine --> news
engine --> hybrid
engine --> lstm
engine --> trader
sent --> news
sent --> hybrid
pred --> lstm
hybrid --> finbert
news --> newsapi
lstm --> yf
trader --> pg
fin --> pg
hybrid --> redis
news --> redis
```

## Data Flow
1. News fetched from NewsAPI and cached in Redis.
2. Sentiment service computes VADER and FinBERT scores and fuses hybrid score.
3. Predictor trains/infers lightweight LSTM on recent market + sentiment features.
4. Trader executes paper trades if hybrid threshold and predictor signal are positive.
5. Finance APIs provide mark-to-market portfolio and benchmark analytics.

## Research Mapping
- Hybrid weighting (`0.4 VADER + 0.6 FinBERT`) follows hybrid lexicon+transformer research.
- Predictor consumes both technical and sentiment features, consistent with FinBERT-LSTM-style methodologies.

## Notes
- This is paper-trading only.
- Backtest module currently provides lightweight metrics and should be expanded with transaction costs and walk-forward validation.
