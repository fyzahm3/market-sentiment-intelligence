# Audit report: `momentum`

**Verdict: NO_EDGE**

- Shuffled scores did as well or better 88% of the time (threshold 20%).

Period 2000-01-03 to 2026-10-30 (6748 sessions), long-only top 3, 1 variant(s) tried.

## Data

- Universe: us_sector_etfs: XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY
- Source: yfinance 1.8.0, split/dividend adjusted, downloaded 2026-11-17T15:41:18Z, sha256 cd06693fc60f4ba41f69a0334bcfed4f235f1486d4dd2549a5c6a9182cf56a1d
- Sessions: 6748, tickers: 9
- Non-positive prices: 0
- Missing ticker-days: 0
- Calendar gaps longer than 4 weekdays: 0
- Split suspects: 0 (adjusted prices; no overnight move near a split ratio)

## Leak check (truncation test)

- Result: passed
- Cut dates tested: 5
- Past scores that changed: 0

## Performance

| Cost (bps) | Total return | CAGR | Sharpe | Sortino | Max drawdown |
|---:|---:|---:|---:|---:|---:|
| 0 | +484.7% | +6.8% | 0.45 | 0.42 | -64.7% |
| 10 | -31.1% | -1.4% | 0.02 | 0.02 | -81.9% |
| 25 | -97.2% | -12.5% | -0.62 | -0.59 | -97.7% |
| buy & hold | +981.9% | +9.3% | 0.57 | 0.55 | -52.6% |

## Statistics

- Permutation p-value: 0.8782 (500 shuffles, before costs)
- Deflated Sharpe at 10 bps: 0.5391

## Checks not run

- Model memory: whether an LLM behind the signal saw this period in training.
- Survivorship: whether the ticker universe was chosen with hindsight.

## Verdict rules

- EDGE_SURVIVES: no leak, p <= 0.05, deflated Sharpe >= 0.95, Sharpe at 25 bps > 0
- NO_EDGE: no leak, and p > 0.2 or Sharpe at 10 bps <= 0
- INCONCLUSIVE: anything else

_This report evaluates a signal. It is not investment advice._
