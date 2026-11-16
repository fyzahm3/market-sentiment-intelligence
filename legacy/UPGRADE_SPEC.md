# Market Sentiment Intelligence Platform — Upgrade Specification

**Purpose of this document:** Implementation spec for upgrading the existing repo
(`fyzahm3/market-sentiment-intelligence`) from a working sentiment→paper-trading pipeline
into a research-grade, production-quality AI market intelligence platform. Written to be
executed phase-by-phase by Claude Code. Each phase is independently shippable.

**Target audience for the final project:** Fintech/SWE/AI-engineering hiring teams in 2026.
The design decisions below map directly to what those teams screen for:
(a) evaluation/eval design, (b) backtest rigor and quant literacy, (c) LLM/agentic systems,
(d) observability + cost awareness, (e) production engineering (Docker, CI, tests, migrations).

---

## 0. Current state of the repo (do not skip reading this)

Already built and working:
- FastAPI backend (`app/main.py`), routers in `app/api/v1/` (`sentiment.py`, `finance.py`)
- NewsAPI headline ingestion (`app/services/news.py`, httpx async)
- VADER sentiment scoring (`app/services/sentiment_analyzer.py`) — avg compound score,
  label thresholds at ±0.05, confidence = abs(avg_score)
- Paper-trading engine (`app/services/trader.py`) with BUY logic (sizing =
  MAX_POSITION_SIZE × score × confidence) AND SELL logic (stop-loss -8%, bearish-flip exit
  gated on confidence ≥0.15, take-profit +15% selling 50%), portfolio exposure cap 30%,
  cash reserve floor 10%
- Hourly batch engine (`app/services/ingestion_engine.py`) — sells checked before buys,
  shared price quote per cycle, performance snapshots (AI fund vs benchmark, alpha)
- Postgres (Supabase) with raw SQL: `portfolio`, `trade_logs`, `sentiment_results`,
  `benchmark_portfolio`, `performance_history`
- React + Vite + Tailwind frontend (basic)

Known weaknesses to fix (in roughly this order of importance):
1. No backtesting — all evaluation is forward-only paper trading (needs weeks to mean anything)
2. No evaluation layer of any kind — sentiment model is unvalidated
3. VADER is not finance-tuned ("beats estimates", "guided down" score wrong)
4. Confidence = abs(avg_score) ignores article volume/consensus entirely
5. No explainability — cannot show which headlines drove a trade
6. Stale README (says Reddit; code uses NewsAPI)
7. Mixed config (some files use `app/core/config.py` Settings, some use raw `os.getenv`)
8. New psycopg2 connection opened per operation — no pooling
9. Zero tests, no CI, no Docker, no migrations (schema is loose .sql files)
10. yfinance `fast_info.last_price` calls are serial and slow; no caching/retry

---

## 1. Positioning (drives all naming/README/docs decisions)

**Project name:** Market Sentiment Intelligence Platform (keep)
**One-line pitch:** "News-driven trading signal engine with a validated multi-model
sentiment layer, rigorous historical backtesting, and an LLM analyst that explains
every trade."

**What it must NOT claim:** market prediction, guaranteed alpha, investment advice.
Position everything as *decision support + signal research*. The README must carry a
research/education disclaimer.

**The three headline differentiators (each phase below builds one):**
1. **Model comparison, not model choice** — pluggable sentiment backends (VADER /
   FinBERT / LLM) benchmarked against each other on a labeled dataset AND by backtest PnL.
2. **Honest backtesting** — event-driven, point-in-time, transaction costs, random-baseline
   comparison, walk-forward splits. The README explicitly names the biases avoided.
3. **Agentic analysis layer** — a bull/bear LLM debate that reviews high-stakes trades,
   with its own eval suite, cost tracking, and full trace logging.

---

## 2. Phase 1 — Engineering foundation (do first, ~1 week of Claude Code sessions)

Goal: make the repo look like it was built by an engineer, not a notebook.

### 2.1 Config unification
- Extend `app/core/config.py` Settings to include: `database_url`, `news_api_key`,
  `anthropic_api_key` (or other LLM key), trading params (stop-loss, take-profit,
  exposure caps — move the constants out of `trader.py`), `environment` (dev/prod).
- Replace every raw `os.getenv` / `load_dotenv` call sitewide with `settings.*`.
- Add `.env.example` with every variable documented.

### 2.2 Database layer
- Introduce a single connection pool (`psycopg2.pool.ThreadedConnectionPool` or move to
  `psycopg` v3 / SQLAlchemy Core — pick one, document why).
- Consolidate the four loose `.sql` files into versioned migrations (Alembic if SQLAlchemy,
  else a simple numbered-migration runner). `init_db.py` becomes `migrate.py`.
- Add new tables needed by later phases (create in this phase so migrations are clean):
  - `articles` (id, ticker, headline, url, source, published_at, fetched_at, dedup_hash)
  - `article_scores` (article_id, model_name, score, label, scored_at)
  - `trade_attributions` (trade_id, article_id, weight) — which headlines drove a trade
  - `agent_reviews` (trade_id, bull_case TEXT, bear_case TEXT, verdict, model, tokens_in,
    tokens_out, cost_usd, latency_ms, created_at)
  - `backtest_runs` (id, strategy_config JSONB, date_range, metrics JSONB, created_at)

### 2.3 Testing + CI
- pytest suite. Priority order:
  1. `trader.py` sizing math + sell trigger priority (stop-loss beats bearish beats take-profit)
  2. exposure cap / cash floor edge cases (portfolio at exactly 30%, cash at exactly 10%)
  3. sentiment aggregation (empty list, single headline, mixed)
  4. API route contract tests with a test DB (or mocked cursor)
- Use dependency injection / fixtures so DB and yfinance are mockable. Refactor
  `trader.py` functions to accept a connection/cursor instead of opening their own —
  this is the enabling refactor for everything testable.
- GitHub Actions: lint (ruff), type-check (mypy, gradual), pytest on every push. Badge in README.

### 2.4 Docker
- `Dockerfile` (multi-stage: deps → app) + `docker-compose.yml` (api, worker/engine,
  postgres, frontend). One-command local spin-up: `docker compose up`.
- Separate the batch engine into its own service/entrypoint rather than `if __name__ == "__main__"`.

### 2.5 README rewrite
- Fix the Reddit claim. Architecture diagram (mermaid). Quickstart. Screenshot/GIF of
  dashboard. Disclaimer. "Known limitations" section (interviewers love honesty here).

**Acceptance criteria for Phase 1:** `docker compose up` runs the full stack; `pytest`
green in CI; no `os.getenv` outside config.py; migrations idempotent.

---

## 3. Phase 2 — Sentiment layer v2: pluggable, finance-tuned, explainable

Goal: replace "I used VADER" with "I benchmarked three model families and can show you
which headlines moved every score."

### 3.1 Pluggable backend interface
```python
class SentimentBackend(Protocol):
    name: str
    def score(self, texts: list[str]) -> list[SentimentScore]  # per-text, not aggregate
```
Implementations:
- `VaderBackend` (existing logic, kept as the fast/free baseline)
- `FinBERTBackend` — HuggingFace `ProsusAI/finbert` (or `yiyanghkust/finbert-tone`),
  batched inference, CPU-friendly, lazy model load, per-headline label+prob
- `LLMBackend` — few-shot prompt to a small/cheap model (e.g. Claude Haiku class),
  strict JSON output {label, score, one-line rationale}, batched N headlines per call,
  response caching keyed on dedup_hash to control cost
Config selects active backend; ingestion writes per-article scores to `article_scores`
for ALL enabled backends (cheap ones always; LLM optionally) so they can be compared later.

### 3.2 Aggregation v2 (fixes the confidence bug)
Per ticker per window compute:
- `score` = credibility-and-recency-weighted mean of per-article scores
  (source credibility: simple tiered map, e.g. Reuters/Bloomberg > aggregators; recency:
  exponential decay over the window)
- `confidence` = f(article_count, inter-article agreement) — e.g. sigmoid(volume) ×
  (1 − normalized std of scores). One strongly-worded headline must no longer equal
  50 agreeing headlines.
- `top_drivers` = top-k |score×weight| article ids → written to `trade_attributions`
  when a trade fires.

### 3.3 Deduplication
- Same story syndicated across outlets currently multi-counts. Dedup on normalized-title
  hash + fuzzy match (rapidfuzz ratio > 90 within window). Store `dedup_hash` in `articles`.

### 3.4 Sentiment evaluation harness (THE resume line)
- Dataset: Financial PhraseBank (free, standard benchmark) + a 100–200 headline hand-labeled
  golden set from the actual pipeline (Fayaz labels these — takes an evening; makes the
  eval defensible as "on my own data distribution", not just a public benchmark).
- `make eval-sentiment` runs all backends against both sets → accuracy, macro-F1,
  per-class precision/recall, confusion matrices, plus cost-per-1k-headlines and latency
  for each backend. Output: markdown report committed to `reports/` + JSON.
- Publish the table in the README. Whatever wins, wins — the *harness* is the flex.

**Acceptance criteria:** three backends behind one interface; eval report reproducible
with one command; per-trade headline attribution visible via API (`/trades/{id}/why`).

---

## 4. Phase 3 — Backtesting engine (the credibility phase)

Goal: replace "my paper fund is up X%" with defensible historical evidence, built the way
a quant reviewer would expect.

### 4.1 Data
- Primary: **FNSPID dataset** (github.com/Zdong104/FNSPID; HuggingFace mirror) —
  time-aligned financial news + prices for S&P500 names, 1999–2023. Use the news
  timestamps as point-in-time anchors; join to daily OHLCV (from the dataset itself or
  yfinance historical downloads cached to parquet).
- Ingest a subset first (the 8 current TARGET_STOCKS, 2018–2023) to keep iteration fast;
  design the loader so the universe/date-range is config.
- Store as parquet in `data/` (gitignored) with a `make fetch-data` script.

### 4.2 Engine design
- **Event-driven, not vectorized-with-shortcuts:** iterate day by day; on each day the
  strategy sees ONLY news published before that day's decision time and ONLY prices up to
  the prior close. Trades execute at next-day open (models the you-can't-trade-on-a-close-
  you-just-observed problem).
- Reuse the live strategy code: extract the decision logic from `trader.py` into a pure
  function `decide(signal, position, portfolio_state, params) -> Order | None` used by BOTH
  the live engine and the backtester. (Single-source-of-truth strategy = a strong
  architecture talking point.)
- **Transaction costs:** configurable, default 10 bps per side + optional fixed slippage.
  Report results at 0 / 10 / 25 bps so sensitivity is visible.
- **Baselines (mandatory, reported side-by-side):**
  1. Buy-and-hold equal-weight of the same universe
  2. SPY buy-and-hold
  3. Random-signal Monte Carlo: N=1000 runs with shuffled/random signals at the same trade
     frequency → the strategy's Sharpe must be reported as a percentile against this
     distribution ("monkey test")
- **Validation protocol:** walk-forward splits (e.g. train/tune params on 2018–2020,
  test 2021; roll forward). Never tune on the reported test window. Log every parameter
  combination tried into `backtest_runs` (an honest trials count — mention Deflated
  Sharpe Ratio in the report even if only computed approximately).

### 4.3 Metrics
Per run: total return, CAGR, annualized Sharpe, Sortino, max drawdown, Calmar,
profit factor, win rate, turnover, exposure %. Store to `backtest_runs.metrics`;
render an equity-curve + drawdown chart (matplotlib PNG into `reports/`, and a
JSON endpoint for the dashboard).

### 4.4 Documentation of rigor (interviewers probe exactly this)
`docs/backtesting.md` must explicitly name and explain how the engine avoids:
look-ahead bias (decision-time filtering, next-open execution), survivorship bias
(state the limitation honestly: fixed mega-cap universe partially sidesteps but does not
eliminate it — say so), overfitting (walk-forward, trials logging, random baseline),
and unrealistic fills (costs + slippage). Honesty about remaining limitations > pretending
they don't exist.

**Acceptance criteria:** `make backtest CONFIG=configs/default.yaml` produces a full
report; strategy and live engine share the same decision function; random-baseline
percentile reported.

---

## 5. Phase 4 — Agentic analysis layer (the 2026 differentiator)

Goal: a scoped, evaluated multi-agent LLM layer — inspired by the TradingAgents research
framework (arXiv 2412.20138) but deliberately smaller and fully instrumented.

### 5.1 Bull/Bear review gate
- Trigger: only for HIGH-STAKES orders (allocation above a configurable threshold, or any
  full-position exit). Everything else trades on the quantitative signal alone — this keeps
  LLM cost bounded and is itself a defensible design decision.
- Flow (LangGraph or a plain hand-rolled state machine — hand-rolled is fine and shows
  understanding; don't add a framework just for two agents):
  1. **Bull agent**: given ticker, the top-driver headlines, current position, recent price
     stats → argues the case FOR the trade (structured JSON: thesis, 3 supporting points,
     confidence 0–1)
  2. **Bear agent**: same inputs + bull's output → argues AGAINST
  3. **Risk arbiter**: both cases + portfolio state → verdict {approve, reduce_size(x%),
     reject} + one-paragraph rationale
- Persist everything to `agent_reviews` including token counts, latency, and cost per review.
- Fail-open design decision, documented: if the LLM call errors/times out, fall back to the
  quantitative decision with a logged warning (availability > marginal judgment).

### 5.2 Evals for the agent layer (do not skip — this is the hiring signal)
- Golden set: 30–50 historical trade scenarios (pull from backtest) with hand-labeled
  "reasonable verdict" ranges.
- Judge harness: LLM-as-judge scoring arbiter rationales for groundedness (does the
  rationale only reference supplied headlines/data?) + a hard programmatic check that JSON
  schema and verdict enums are valid. Track a hallucination/grounding rate.
- Regression: `make eval-agents` runs the golden set on every prompt change; store scores;
  fail CI if grounding rate drops below threshold.
- A/B in backtest: run the same backtest window with and without the agent gate → report
  whether the gate improved risk-adjusted returns or just cost money. EITHER result is a
  great interview story; report it honestly.

### 5.3 Cost + prompt engineering notes
- Cache few-shot prefixes (prompt caching if using Anthropic API). Batch where possible.
- Track cumulative LLM spend in a `/api/v1/costs` endpoint and on the dashboard.
- Target: an entire backtest-with-agents run on 8 tickers × 1 year should cost single-digit
  dollars — document the actual number.

**Acceptance criteria:** agent gate live behind config flag; every review fully traced in
DB; `make eval-agents` green; with/without-gate backtest comparison in the report.

---

## 6. Phase 5 — Observability, dashboard, deployment polish

### 6.1 Observability
- Structured logging (structlog or std logging + JSON formatter) everywhere; kill the
  emoji-print debugging in services (fine in CLI output, not in service code).
- OpenTelemetry traces for: ingestion cycle, each backend scoring call, each LLM agent
  call (span per agent), DB operations. Export to console/OTLP; Langfuse optionally for
  the LLM spans specifically.
- `/health` and `/metrics` endpoints; engine cycle duration, API error rate, news-fetch
  failure count.

### 6.2 Dashboard upgrades (React, keep it focused — 4 views max)
1. **Portfolio**: holdings, equity curve vs benchmark (exists — polish)
2. **Signals**: per-ticker sentiment timeline with article-volume bars; click a point →
   the driver headlines (explainability surfaced to UI)
3. **Trade log**: every trade with its "why" (attributed headlines + agent verdict &
   rationale when present)
4. **Research**: backtest run browser — pick a run, see metrics + equity/drawdown charts
   + config diff vs another run

### 6.3 Deployment
- Deploy API+worker on a free/cheap tier (Railway/Fly/Render), frontend on Vercel/Netlify,
  DB stays Supabase. Live demo URL in README.
- K3s manifests in `deploy/k8s/` as an optional path — this connects directly to the
  Truminds K3s/Docker experience and is worth a sentence in interviews even if the live
  demo runs on Railway.

---

## 7. Execution order & scoping guidance for Claude Code

- Phases are ordered by dependency AND by interview ROI. If time-boxed, the minimum
  "extraordinary" cut is: Phase 1 → Phase 2 (incl. 3.4-style eval) → Phase 3.
  Phase 4 is the differentiator if placement timeline allows; Phase 5.2/5.3 can be trimmed.
- Work in small PRs per subsection with descriptive commit messages — the git history is
  itself reviewed by some interviewers.
- Never fabricate metric numbers anywhere (README, reports, resume). Every number must be
  reproducible by a `make` target.
- Keep the 8-ticker universe until everything works end-to-end; widening the universe is a
  config change, not a milestone.

---

## 8. Resume bullets (fill numbers ONLY from real, reproducible runs)

- Built an end-to-end market intelligence platform (FastAPI, Postgres, React) that scores
  financial news with pluggable sentiment backends — benchmarked VADER, FinBERT, and an
  LLM few-shot classifier at __% / __% / __% macro-F1 on Financial PhraseBank plus a
  hand-labeled production golden set.
- Implemented an event-driven backtesting engine with point-in-time news alignment
  (FNSPID, __ articles / __ tickers), next-open execution, and transaction-cost modeling;
  strategy Sharpe of __ vs buy-and-hold __ and a 1,000-run random-signal baseline
  (__ th percentile).
- Designed a bull/bear/risk-arbiter LLM agent gate for high-stakes trades with a golden-set
  eval harness (grounding rate __%), full token/cost tracing (avg $__ per review), and an
  A/B backtest quantifying the gate's impact on risk-adjusted returns.
- Shipped with pytest CI, Alembic migrations, Docker Compose, OpenTelemetry tracing, and a
  live dashboard exposing per-trade headline attribution.

## 9. Interview defense cheat-sheet (know these answers cold)

- "Why did/didn't the strategy beat buy-and-hold?" → answer from the walk-forward report;
  discuss regime dependence; cite the random-baseline percentile.
- "How do you know it's not overfit?" → walk-forward, trials logging, random baseline,
  costs sensitivity; acknowledge remaining risk (short history, small universe).
- "Why FinBERT / why not just GPT?" → show YOUR eval table; discuss cost/latency/accuracy
  tradeoff — research is split (FinBERT wins on PhraseBank in several studies; LLMs win on
  return prediction in others), which is exactly why the pipeline benchmarks instead of assuming.
- "What breaks in production?" → NewsAPI rate limits, yfinance flakiness (retry/backoff),
  LLM timeouts (fail-open gate), DB pool exhaustion — and where each is handled in code.
- "What would you do with more time?" → intraday data, options-implied sentiment cross-check,
  drift monitoring on sentiment distributions, broader survivorship-bias-free universe.

## 10. Reference material used for this spec

- TradingAgents: Multi-Agents LLM Financial Trading Framework — arXiv:2412.20138,
  github.com/TauricResearch/TradingAgents (multi-agent architecture inspiration)
- FNSPID dataset — arXiv:2402.06698, github.com/Zdong104/FNSPID (backtest data)
- ProsusAI/finBERT — github.com/ProsusAI/finBERT; Financial PhraseBank (eval benchmark)
- Financial Sentiment Analysis with LLMs and FinBERT — arXiv:2410.01987 (model comparison)
- Sentiment trading with LLMs — Finance Research Letters 2024 (LLM signal performance)
- Backtesting pitfalls: Harvey (Duke) backtesting paper; Bailey & López de Prado, Deflated
  Sharpe Ratio; Wiecki et al. 2016 (Quantopian 888-algo study)
