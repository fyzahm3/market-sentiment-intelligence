from datasets import load_dataset
import pandas as pd

print("Loading dataset from Hugging Face...")
dataset = load_dataset("NickyNicky/finance-financialmodelingprep-stock-news-sentiments-rss-feed")
df = dataset["train"].to_pandas()

tickers = ["AAPL", "TSLA", "GOOGL", "AMZN", "MSFT", "NVDA", "META", "NFLX"]
filtered_df = df[df["symbol"].isin(tickers)].copy()

print(f"Total rows in dataset: {len(df)}")
print(f"Filtered rows (our 8 tickers): {len(filtered_df)}")

if not filtered_df.empty:
    filtered_df["publishedDate"] = pd.to_datetime(filtered_df["publishedDate"])
    min_date = filtered_df["publishedDate"].min()
    max_date = filtered_df["publishedDate"].max()
    print(f"Date range: {min_date} to {max_date}")
    
    print("\nRows per ticker:")
    print(filtered_df["symbol"].value_counts())
else:
    print("No rows found for target tickers!")
