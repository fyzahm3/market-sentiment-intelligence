import os
import sys
import pandas as pd
import numpy as np
import yfinance as yf
from datasets import load_dataset
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import nltk
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

# Set paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.core.config import settings

# Create data directory if it doesn't exist
os.makedirs("data", exist_ok=True)

# 1. Download and Filter News
print("Loading financial RSS news feed from Hugging Face...")
dataset = load_dataset("NickyNicky/finance-financialmodelingprep-stock-news-sentiments-rss-feed")
df = dataset["train"].to_pandas()

tickers = settings.target_stock_list
print(f"Filtering dataset for target stocks: {tickers}...")
filtered_df = df[df["symbol"].isin(tickers)].copy()
print(f"Found {len(filtered_df)} news records.")

# Normalize Date to YYYY-MM-DD
filtered_df["date"] = pd.to_datetime(filtered_df["publishedDate"]).dt.date

# 2. VADER Sentiment Ingestion
print("Computing VADER sentiment scores...")
try:
    nltk.data.find('sentiment/vader_lexicon.zip')
except LookupError:
    nltk.download('vader_lexicon')

sia = SentimentIntensityAnalyzer()
vader_scores = []
for title in filtered_df["title"]:
    vader_scores.append(sia.polarity_scores(str(title))["compound"])
filtered_df["vader_score"] = vader_scores

# 3. FinBERT Ingestion (Hardware Accelerated if available)
device = torch.device("mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu"))
print(f"Loading FinBERT model on device: {device}...")

tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
model = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert")
model.to(device)
model.eval()

finbert_scores = []
batch_size = 64
titles = filtered_df["title"].astype(str).tolist()

print(f"Scoring {len(titles)} headlines in batches of {batch_size}...")
with torch.no_grad():
    for i in range(0, len(titles), batch_size):
        batch_titles = titles[i : i + batch_size]
        encoded = tokenizer(batch_titles, padding=True, truncation=True, max_length=128, return_tensors="pt")
        encoded = {k: v.to(device) for k, v in encoded.items()}
        outputs = model(**encoded)
        probs = torch.softmax(outputs.logits, dim=-1)
        # FinBERT labels: Index 0 is positive (1.0), Index 1 is negative (-1.0), Index 2 is neutral (0.0)
        sentiment_values = torch.tensor([1.0, -1.0, 0.0], device=device)
        weighted = torch.matmul(probs, sentiment_values)
        finbert_scores.extend(weighted.cpu().tolist())

        if (i // batch_size) % 10 == 0:
            print(f"Processed {min(i + batch_size, len(titles))} / {len(titles)} headlines...")

filtered_df["finbert_score"] = finbert_scores

# Calculate hybrid sentiment
v_weight = settings.sentiment_vader_weight
f_weight = settings.sentiment_finbert_weight
filtered_df["hybrid_score"] = v_weight * filtered_df["vader_score"] + f_weight * filtered_df["finbert_score"]

# Group by Date and Symbol to get Daily Average Sentiment
print("Grouping news sentiment by day and ticker...")
daily_sentiment = filtered_df.groupby(["date", "symbol"]).agg(
    vader_score=("vader_score", "mean"),
    finbert_score=("finbert_score", "mean"),
    hybrid_score=("hybrid_score", "mean"),
    article_count=("title", "count")
).reset_index()

# Save Sentiment to Parquet
sentiment_file = "data/historical_sentiment.parquet"
daily_sentiment.to_parquet(sentiment_file)
print(f"Saved daily sentiment data to {sentiment_file}")

# 4. yfinance Price Download
min_date = filtered_df["date"].min()
max_date = filtered_df["date"].max()
# Pad dates by a few days to make sure we don't miss start/end boundaries
start_date = (min_date - pd.Timedelta(days=5)).strftime("%Y-%m-%d")
end_date = (max_date + pd.Timedelta(days=5)).strftime("%Y-%m-%d")

print(f"Downloading historical stock price data from {start_date} to {end_date}...")
prices_df_list = []
for ticker in tickers + ["SPY"]:
    print(f"Downloading prices for {ticker}...")
    t = yf.Ticker(ticker)
    hist = t.history(start=start_date, end=end_date)
    if not hist.empty:
        hist = hist.reset_index()
        hist["symbol"] = ticker
        prices_df_list.append(hist)

if prices_df_list:
    prices_df = pd.concat(prices_df_list, ignore_index=True)
    # Standardize columns
    prices_df = prices_df[["Date", "Open", "High", "Low", "Close", "Volume", "symbol"]]
    prices_df["Date"] = pd.to_datetime(prices_df["Date"]).dt.date
    prices_file = "data/historical_prices.parquet"
    prices_df.to_parquet(prices_file)
    print(f"Saved historical prices data to {prices_file}")
else:
    print("Error: Could not download stock prices.")

print("Data download and preprocessing completed successfully!")
