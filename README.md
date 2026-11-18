# Signal Audit Lab

Tests whether a news or social-media trading signal has a real edge, and keeps a
tamper-evident forward record of predictions.

> **Status: M3, forward ledger live for price-only signals.** The engine audits
> price-only signals on real US sector ETF prices, and a daily job records their
> predictions before the next open. Text-based signals have not been audited on
> real data yet (M2 waits on Reddit API access). Nothing here is investment
> advice.

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
- **NYSE calendar.** Sessions, holidays, special closures and 13:00 early
  closes come from the NYSE calendar, so "close of T" is the true close.
- **Forward ledger.** Append-only, hash-chained log that rejects predictions
  made after the outcome window opens. `sigaudit ledger record` adds the
  latest session's prediction; `sigaudit ledger score` appends the realised
  return of each finished prediction to a separate hash-chained outcomes file.

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

## Live ledger

A scheduled GitHub Actions job (`.github/workflows/ledger.yml`) runs on
weekdays at 21:30 UTC, after the New York close. It:

1. records the scores of `momentum` and `random` on
   `universes/us_sector_etfs.txt` for the session that just closed, using
   freshly downloaded yfinance prices (top 3, long-only);
2. scores every prediction whose holding period has ended: bought at the open
   of the next session, sold at the open of the session after that, before
   costs and at 10 bps;
3. verifies both files and commits them.

Predictions are in `records/ledger.jsonl` and outcomes in
`records/outcomes.jsonl`; the job creates both on its first run. Each line carries the
hash of the line before it, each outcome names the prediction it scores by
hash, and the git history timestamps every commit. A prediction made after the
next open is refused. On a holiday there is no new session, so nothing is
committed. `random` is there as a control: it should not beat chance.

Anyone can check that nothing has been edited, removed or back-dated:

```bash
make setup
uv run sigaudit ledger verify
```

The same steps run locally with `make ledger-record`, `make ledger-score` and
`make ledger-verify` (network access needed for the first two). The record is
too short to say anything yet; no performance figures are quoted here.

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
records/            forward ledger and outcomes, committed by the daily job
data/labels/        small labelled datasets
data/cache/         downloaded prices (gitignored)
legacy/             the earlier trading-bot version of this project, kept for reference
```

## Roadmap

Real prices (done), the live forward ledger for price-only signals (done),
then Reddit data and a public site. Milestones and acceptance criteria are in
[docs/SPEC.md](docs/SPEC.md).

## Limitations

- Only one real-price report exists, for a price-only signal. No text-based
  signal has been audited on real data yet.
- The forward ledger covers price-only signals only. A session whose prices are
  not available when the daily job runs is skipped and cannot be added later.
- Long-only, top-k portfolios only.
- The leak check cannot detect a model that memorised the future, or a ticker
  universe chosen with hindsight. The momentum report lists both as checks not
  run.
- The leak check sees engagement (post scores, comment counts) only when it is
  stored as timestamped snapshots. An archive's final value stamped with the
  posting time looks like ordinary data and cannot be detected.
