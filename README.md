# Signal Audit Lab

Tests whether a news or social-media trading signal has a real edge, and keeps a
tamper-evident forward record of predictions.

> **Status: scaffold.** The audit engine runs on synthetic data only. There are
> no real-market results yet, and nothing here is investment advice.

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

## Layout

```
src/signal_audit/   library and CLI
tests/              test suite (no network)
docs/               PRD.md (what and why), SPEC.md (how)
data/labels/        small labelled datasets
legacy/             the earlier trading-bot version of this project, kept for reference
```

## Roadmap

Real prices, then Reddit data, then the live forward ledger and a public site.
Milestones and acceptance criteria are in [docs/SPEC.md](docs/SPEC.md).

## Limitations

- Synthetic data only so far.
- Every weekday is treated as a trading session; market holidays are not handled.
- Long-only, top-k portfolios only.
- The leak check cannot detect a model that memorised the future, or a ticker
  universe chosen with hindsight.
