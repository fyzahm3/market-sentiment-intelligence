# Backtesting Strategy & Methodological Limitations

This document outlines the methodology, validation steps, and technical limitations of the event-driven backtesting engine implemented in the Market Sentiment Intelligence Platform. Identifying and documenting these limitations is essential for ensuring models are not overfitted to historical noise and can be safely deployed in production.

---

## 1. Backtesting Engine Design

The backtesting engine is designed as an **event-driven daily simulation** covering the 8-ticker target universe (`AAPL`, `TSLA`, `GOOGL`, `AMZN`, `MSFT`, `NVDA`, `META`, `NFLX`) from **August 2022 to October 2023** (using the Financial Modeling Prep stock news RSS feed).

- **Execution Model:** Signals are calculated daily on day $T$ using news and closing prices available up to day $T$. Trades are executed at the **Open price of day $T+1$**.
- **Transaction Costs:** A slippage and fee cost of **10 basis points (bps) per transaction** (0.10% of total volume) is applied to both entry and exit trades.
- **Risk Management:** The strategy strictly caps single-stock exposure at **30% of total portfolio net asset value** and maintains a **10% cash reserve floor** to avoid margin calls and over-concentration. It enforces a **5% stop-loss** and **15% take-profit** exit rule.

---

## 2. Methodological Limitations & Mitigations

### 2.1 Look-Ahead Bias (Mitigated)
* **Definition:** Using information from the future to make decisions in the past (e.g. trading at the close price of day $T$ using a signal that incorporates news published after the close).
* **Mitigation:** Fully resolved. The simulation strictly iterates through time step-by-step. On day $T$, the decision engine only sees news published on or before day $T$. Orders are placed at the market close of day $T$ and are executed at the **Open price of day $T+1$**, preventing execution on prices that occurred prior to or during the signal generation period.

### 2.2 Survivorship Bias (Unsolved)
* **Definition:** Evaluating the strategy only on companies that are currently trading and active (e.g. our 8-ticker tech stock universe), while omitting companies that went bankrupt, merged, or were delisted during the backtest window.
* **Status in this project:** **Unsolved.** The backtest is run on a static universe of 8 highly successful tech companies. This introduces a positive selection bias, as these companies survived and flourished over the backtest window. In a production institutional backtest, the universe would dynamically change based on historical S&P 500 index constituents.

### 2.3 Overfitting & Data Snooping (Mitigated)
* **Definition:** Tuning hyperparameters (e.g., sentiment thresholds, allocation weight, stop-loss percentages) on the exact same data that is used to evaluate the strategy, creating an artificially high return profile.
* **Mitigation:** Handled via a **Walk-Forward Split**:
  - The parameter optimization is restricted to the **Tuning window** (first 35% of the dates: August 2022 to December 2022).
  - The final performance and metrics are reported exclusively on the **Out-of-sample Testing window** (remaining 65% of the dates: January 2023 to October 2023).
  - Additionally, we run a **1,000-run Random-Signal Monte Carlo simulation** by shuffling the historical signals. The strategy's Sharpe ratio is reported as a percentile rank against this distribution. If the strategy does not exceed the 95th percentile, its performance can be attributed to lucky noise rather than statistical edge.

### 2.4 Short Historical Window (Limitation)
* **Definition:** Backtesting over a limited period (14 months) which may represent a specific market regime (e.g., a bull market or specific interest-rate environment) and might not generalize to other regimes.
* **Status in this project:** Documented. Because high-quality time-aligned stock headlines are computationally expensive to parse and query, the backtest window is limited to the parsed Hugging Face RSS feed dataset. We acknowledge that performance metrics might differ in highly bearish periods (e.g., 2008 or 2022 market crashes).
