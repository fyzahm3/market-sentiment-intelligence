# Signal Audit Lab — Product Requirements

| | |
|---|---|
| Status | Draft v0.1 |
| Date | 2026-11-16 |
| Owner | Fayaz Ahmed |
| Working name | Signal Audit Lab (package `signal_audit`, CLI `sigaudit`) |

> **Not investment advice.** This product evaluates whether a signal's claimed
> performance is statistically credible. It does not recommend trades.

---

## 1. Summary

Signal Audit Lab tells a person whether a news or social-media trading signal has
a real edge before they risk money on it. It does this in two ways:

1. **Audit:** run the signal through leak detection, realistic costs, baselines
   and multiple-testing-aware statistics, and return a one-page report card with
   a plain verdict.
2. **Forward ledger:** log the signal's predictions *before* outcomes are known
   in a tamper-evident public record, and score them as outcomes arrive.

## 2. Problem

People who build or follow a news/social trading signal have no free,
independent way to find out whether it is real. They rely on a backtest they
wrote themselves, or on a vendor or influencer's unaudited claim.

### 2.1 Evidence

| Claim | Evidence | Source |
|---|---|---|
| Backtests don't predict live results | Across 888 strategies, backtest Sharpe explained roughly 1–2% of out-of-sample performance; more backtests run meant a bigger in-sample/out-of-sample gap | Wiecki et al., "All that Glitters Is Not Gold" (Quantopian) |
| LLM trading claims mostly fail proper testing | Reported LLM strategy edges largely vanish over 20 years with survivorship and look-ahead controls | FINSABER, arXiv 2505.07078 |
| Leaks can live in the model, not just the data | LLMs remember historical outcomes ("parametric look-ahead bias"), which input-side controls miss | FinCAD, arXiv 2605.24564; MemGuard-Alpha, arXiv 2603.26797 |
| General LLM quality doesn't transfer to trading | 50-day live evaluation of 21 LLMs: weak-to-negative correlation between general benchmark rank and trading results | LiveTradeBench, arXiv 2511.03628 |
| Social signals are sold without track records | No published forward performance found for ApeWisdom, SwaggyStocks, Quiver Quantitative or StockGeist | Web search, Nov 2026 (absence of evidence; re-check) |
| Evidence on Reddit signals is mixed | Positive results cluster around meme-stock episodes and 3–14 day horizons; other studies find weak or no correlation | Assorted theses and papers, see §12 |
| People act on unverified calls | ~35% of surveyed Canadian retail investors made a decision based on finfluencer advice; a large StockTwits study found most popular finfluencers had negative skill | OSC-linked study; Swiss Finance Institute paper via Edison Group (secondary) |

Figures marked secondary come from summaries, not the primary paper. Verify
against the primary source before quoting them publicly.

### 2.2 Current practice and its gaps

| Current option | Does well | Leaves out |
|---|---|---|
| Backtesting frameworks (Backtrader, vectorbt, Zipline) | Run a strategy on history | Trust whatever data they are fed; give no verdict on credibility |
| Static leak linters (Backtest Auditor, backtest-audit, Flox, leakguard-mcp) | Scan code for obvious look-ahead patterns | Heuristic by their own docs; cannot see leaks in data timestamps or model memory |
| Freqtrade `lookahead-analysis` | Re-runs with truncated data to catch real leaks | Tied to Freqtrade; no text data |
| FINSABER | Rigorous long-horizon LLM strategy evaluation | Academic framework; costly to run; no live record; not a product |
| LiveTradeBench | Live evaluation of LLMs | Ranks models, not a user's signal |
| Numerai Signals | Scores uploaded signals on forward returns | Scored for Numerai's needs; ~1 month to score; explains nothing about a flawed backtest |
| Reddit trackers (ApeWisdom, Quiver, SwaggyStocks) | Show what is trending | Measure attention; publish no forward record |

### 2.3 What is and is not new

Truncation testing, deflated Sharpe and forward ledgers are all known
techniques. The gap is their **combination for text-derived signals**: recorded
knowledge timestamps, a behavioural leak test that works on any signal,
honest statistics, and a public tamper-evident forward record, free to run.
This is a product and engineering gap, not a research invention, and the
README must describe it that way.

## 3. Goals and non-goals

### Goals
- G1. Any signal expressed as "scores per ticker per day" can be audited with one command.
- G2. The audit catches look-ahead leaks by behaviour, not by reading code.
- G3. Every number shown is reproducible from one documented command.
- G4. A public forward ledger whose history cannot be silently rewritten.
- G5. Runs end to end at $0/month.

### Non-goals
- Recommending trades or managing money.
- Order execution or brokerage integration.
- Intraday or high-frequency signals (daily bars only in v1).
- Markets other than US equities in v1.
- Beating the market. A credible "no edge" verdict is a successful audit.

## 4. Users

| Persona | Situation | What they need |
|---|---|---|
| **Builder** (primary) | Writes trading bots; posts on r/algotrading; has a backtest that looks too good | A fast, credible check of whether the backtest is lying |
| **Researcher / student** | Replicating or extending a sentiment paper | Point-in-time data handling and honest statistics out of the box |
| **Sceptical follower** | Follows a Reddit-derived or vendor signal | A public record showing whether that kind of signal has worked forward |
| **Reviewer** (recruiter, interviewer) | Has 5 minutes to judge the project | A live site, a reproducible result, and clean code |

Distribution is through online communities (r/algotrading, Hacker News, X).
There are no warm contacts, so the tool must be useful within one command of
installing it.

## 5. User stories

- As a builder, I run `sigaudit audit my_signal.py` and get a verdict:
  leak detected, no edge, inconclusive, or edge survives.
- As a builder, when a leak is found I am shown the first date and ticker where
  my signal changed once future data was removed.
- As a builder, I see my result at 0, 10 and 25 bps so I know how fragile it is.
- As a researcher, I load Reddit posts and can ask "what was known at the close
  on date D" without writing timestamp logic myself.
- As a follower, I open the public site and see each tracked signal's forward
  record, with every prediction timestamped before its outcome.
- As a reviewer, I clone the repo, run `make check`, and everything passes.

## 6. Requirements

Priority: **P0** = v1 must-have, **P1** = v1 should-have, **P2** = later.

### 6.1 Data
| ID | Requirement | Pri |
|---|---|---|
| D1 | Every stored record carries `event_time` (when it happened) and `knowledge_time` (when we could first have known it), both UTC | P0 |
| D2 | A store that answers "as of time T" using `knowledge_time` only | P0 |
| D3 | Daily US equity prices (open, close) from a free source | P0 |
| D4 | Reddit posts via the official API, ticker-tagged | P0 |
| D5 | Historical Reddit data from open archives, with a declared knowledge lag | P1 |
| D6 | News headlines (RSS/GDELT) and SEC filing timestamps (EDGAR) | P1 |
| D7 | X data | P2 (blocked by $0 budget; pay-per-read) |
| D8 | Point-in-time index membership to remove survivorship bias | P2 |

### 6.2 Signals
| ID | Requirement | Pri |
|---|---|---|
| S1 | One interface: given market data, return scores per date per ticker | P0 |
| S2 | Built-in reference signals: momentum, random, Reddit mention spike | P0 |
| S3 | Sentiment signal using a local model (FinBERT) | P1 |
| S4 | Sentiment signal using an LLM, restricted to documents after the model's training cutoff | P1 |
| S5 | Load a user's signal from a Python file or a CSV of scores | P1 |

### 6.3 Audit
| ID | Requirement | Pri |
|---|---|---|
| A1 | Truncation test: recompute the signal with future data removed and flag any change in past scores | P0 |
| A2 | Backtest convention fixed: decide at close of day T, trade at open of T+1 | P0 |
| A3 | Transaction costs applied to turnover; results reported at 0/10/25 bps | P0 |
| A4 | Baselines: equal-weight buy-and-hold, and a permutation test giving a p-value | P0 |
| A5 | Deflated Sharpe ratio accounting for the number of variants tried | P0 |
| A6 | Report card (Markdown + JSON) with a single verdict and the reason for it | P0 |
| A7 | Planted-leak suite: known-leaky and known-honest signals with expected outcomes | P0 |
| A8 | Model-cutoff check for LLM-based signals | P1 |
| A9 | Walk-forward splits and regime breakdown | P1 |

### 6.4 Forward ledger
| ID | Requirement | Pri |
|---|---|---|
| L1 | Append-only log; each entry hash-chained to the previous one | P0 |
| L2 | Reject entries made after the outcome window opens | P0 |
| L3 | Daily scheduled job records predictions and commits them to git | P1 |
| L4 | Scoring job fills in realised outcomes without altering predictions | P1 |
| L5 | Anyone can verify the chain with one command | P0 |

### 6.5 Surface
| ID | Requirement | Pri |
|---|---|---|
| U1 | CLI: `demo`, `leak-suite`, `audit`, `ledger verify` | P0 |
| U2 | Static public site: leaderboard, per-signal report cards, ledger | P1 |
| U3 | Hosted "upload a CSV, get a report card" | P2 |

### 6.6 Engineering
| ID | Requirement | Pri |
|---|---|---|
| E1 | Tests, lint, type checks run in CI on every push | P0 |
| E2 | All randomness seeded; results reproducible | P0 |
| E3 | No secrets in the repo or in git config | P0 |
| E4 | README numbers generated by commands, never typed by hand | P0 |

## 7. Success metrics

These are chosen so the project can succeed whether or not any signal is profitable.

| Metric | Target | How measured |
|---|---|---|
| Leak detection recall | 100% of planted leaks flagged | `make leak-suite` |
| Leak false positives | 0 honest reference signals flagged | `make leak-suite` |
| Replication | One published result reproduced within a stated tolerance | Documented notebook/command |
| Ledger integrity | 100% of entries verify; 0 late entries | `sigaudit ledger verify` |
| Forward record length | ≥ 60 trading days by the time of applications | Ledger |
| Sentiment eval | F1, cost and latency per model on a labelled set | `make eval-sentiment` (P1) |
| External use | ≥ 1 audit run by someone other than the author | Issue, post or star with evidence |
| Signal results | All pre-registered signals reported, pass or fail | Report cards |

If a pre-registered signal earns an "edge survives" verdict, that becomes the
headline. It is not a requirement.

## 8. Data sources and compliance

| Source | Access | Constraint |
|---|---|---|
| Prices | Free APIs (yfinance) | Unofficial; adjust for splits; cross-check a sample |
| Reddit | Official Data API, OAuth | Free only for approved non-commercial use; apply early. Third-party reports of access winding down by March 2027 are unconfirmed — check Reddit's terms |
| Reddit history | Open archives | Knowledge time is inferred, so results carry that assumption |
| News | RSS, GDELT | Publication time vs. crawl time must be kept separate |
| Filings | SEC EDGAR | Official and free; has an acceptance timestamp |
| X | Pay-per-read API | Out of scope at $0 |

Rules: official routes first. Scraping only public pages, respecting
robots.txt and rate limits, with no login or bot-protection bypass. Store
ticker-level aggregates in the public repo, not raw user content.

## 9. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| No signal shows an edge | High | Low | Success metrics don't depend on it; report honestly |
| Reddit API access denied or withdrawn | Medium | High | Adapter interface; archives and news as fallback |
| Free price data errors | Medium | Medium | Sanity checks; spot-check against a second source |
| Truncation test misses a leak class | Medium | High | Planted-leak suite grows with each new leak found |
| Seen as "yet another backtester" | Medium | Medium | Lead with the verdict and the live ledger, not the backtest |
| Ledger trust questioned | Low | Medium | Hash chain plus public git history |
| Legal: read as investment advice | Low | High | Clear disclaimers; evaluate signals, never recommend trades |

## 10. Milestones

| # | Milestone | Done when |
|---|---|---|
| M0 | Scaffold | Package, tests, CI, demo and leak suite run on synthetic data |
| M1 | Real prices | Audit a momentum signal on real US prices; report card committed |
| M2 | Reddit data | Mention-spike signal built on point-in-time Reddit data and audited |
| M3 | Forward ledger live | Daily job running; ledger verifies; first entries scored |
| M4 | Public site | Leaderboard and report cards online |
| M5 | Sentiment signals | FinBERT and LLM signals with model evals |
| M6 | Launch | README finalised from generated numbers; posted to communities |

M3 is on the critical path for the forward record. Start it as early as
possible, with whatever signals exist.

## 11. Open questions

1. Final product name.
2. Licence (MIT suggested, for community adoption).
3. Which published result to replicate for the replication metric.
4. The pre-registered signal list (3–5 signals) and their exact definitions.
5. Whether the labelled headline set in `data/labels/` was really hand-labelled
   from ingested news; its provenance needs confirming before it is cited.

## 12. Sources

- Wiecki, Campbell, Lent, Stauth — *All that Glitters Is Not Gold* (SSRN 2745220)
- FINSABER — https://arxiv.org/pdf/2505.07078
- FinCAD — https://arxiv.org/pdf/2605.24564.pdf
- MemGuard-Alpha — https://arxiv.org/pdf/2603.26797
- LiveTradeBench — https://www.arxiv.org/pdf/2511.03628
- Numerai Signals docs — https://docs.numer.ai/numerai-signals/signals-overview
- Freqtrade lookahead analysis — https://codeclimate.com/github/freqtrade/freqtrade/docs/lookahead-analysis.md/source
- Backtest Auditor — https://socket.dev/pypi/package/backtest-auditor
- Edison Group on finfluencers — https://www.edisongroup.com/thematic/edison-explains-finfluencers-trending-or-toxic/BM-2759/
- Reddit sentiment studies — https://arxiv.org/abs/2507.22922 ; https://link.springer.com/content/pdf/10.1007/s42521-023-00084-y.pdf
- ICE Reddit-derived backtest — https://www.ice.com/insights/backtesting-a-reddit-derived-strategy-using-ice-signals-and-sentiment-data
- X API pricing change — https://opentermsarchive.org/en/memos/x-replaces-its-dollar200-entry-level-api-plan-with-a-pay-per-use-model/
- Reddit API terms summary — https://data365.co/blog/reddit-api-pricing
