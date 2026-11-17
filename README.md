# Signal Audit Lab

Tests whether a news or social-media trading signal has a real edge, and keeps a
tamper-evident forward record of predictions.

> **Status: M1, first real-price audit.** The engine now audits price-only
> signals on real US sector ETF prices. Text-based signals have not been audited
> on real data yet. Nothing here is investment advice.

## Why

Backtests are easy to get wrong and hard to check. Signals built from news and
social posts are especially prone to look-ahead: a post gets counted on the day
it was written rather than the day it could have been seen. Signal Audit Lab
gives one answer per signal: leak detected, no edge, inconclusive, or edge
survives. See [docs/PRD.md](docs/PRD.md) for the problem, evidence and
comparison with existing tools.

## What it does today

- **Truncation test.** Recomputes a signal with the future removed and flags
  any past score that changes. Works on any signal as a black box.
- **Fixed backtest convention.** Decide at the close of day T, trade at the
  open of T+1, pay costs on turnover.
- **Honest statistics.** Permutation p-value, deflated Sharpe ratio, and
  results at 0, 10 and 25 bps.
- **Report card.** One verdict with the reasons for it, as Markdown and JSON.
- **Real-price audit.** Audits a price-only signal on daily adjusted prices
  downloaded from yfinance. Price sanity checks run first: non-positive prices
  and suspected unadjusted splits stop the audit; missing ticker-days and long
  calendar gaps are reported.
- **Forward ledger.** Append-only, hash-chained log that rejects predictions
  made after the outcome window opens.

## Quickstart

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
make setup
```

```bash
make check
```

```bash
make demo
```

```bash
make leak-suite
```

`make demo` audits four reference signals on a synthetic market that has a
known planted effect. `make leak-suite` runs the leak check against signals
whose leak status is known in advance and exits non-zero if any is misjudged.

To audit a signal on real prices, run:

```bash
make report-momentum
```

This needs network access. It downloads prices via yfinance into the
gitignored cache `data/cache/`, then writes `reports/momentum_us_sector_etfs.md`
and `.json`. The same audit can be run directly:

```bash
uv run sigaudit audit --signal momentum --universe universes/us_sector_etfs.txt \
  --start 2000-01-01 --end 2026-10-31 --top-k 3 --permutations 500 --seed 0 \
  --n-trials 1 --out reports
```

`--end` is exclusive. Add `--refresh` to re-download the prices instead of
using the cache. The cache is fingerprinted with SHA-256, the fingerprint is
printed on the report card, and a tampered cache fails loudly.

## First real result

The first real-price report is
[reports/momentum_us_sector_etfs.md](reports/momentum_us_sector_etfs.md). Its
verdict is `NO_EDGE`.

The signal is a 20-session momentum score on the nine original Select Sector
SPDR ETFs, holding the top 3 long-only. The parameters were fixed before the
result was seen and were not tuned afterwards. The report covers 2000 to 2026
and includes the data checks, the truncation test, the permutation test and
the cost sensitivity. Read the report itself for the numbers.

## Layout

```
src/signal_audit/   library and CLI
tests/              test suite (no network)
docs/               PRD.md (what and why), SPEC.md (how)
universes/          ticker universe files, one per line
reports/            committed report cards (Markdown and JSON)
data/labels/        small labelled datasets
data/cache/         downloaded prices (gitignored)
legacy/             the earlier trading-bot version of this project, kept for reference
```

## Roadmap

Real prices (done), then Reddit data, then the live forward ledger and a public
site. Milestones and acceptance criteria are in
[docs/SPEC.md](docs/SPEC.md).

## Limitations

- Only one real-price report exists, for a price-only signal. No text-based
  signal has been audited on real data yet.
- Market holidays are handled for price-only data, because sessions come from
  the real price index. The weekday-only calendar still applies when documents
  are used.
- Long-only, top-k portfolios only.
- The leak check cannot detect a model that memorised the future, or a ticker
  universe chosen with hindsight. The momentum report lists both as checks not
  run.
