# Execution Plan — UPGRADE_SPEC.md mapped onto the current repo

**Status of this doc:** planning only, no code changes yet. This maps every phase of
`UPGRADE_SPEC.md` against what the repo *actually* contains today (including the large
uncommitted rewrite) and turns it into an ordered, PR-sized checklist.

**Standing decisions (from planning):**
- **Keep the LSTM predictor and JWT auth.** They are not in the spec, but we build the
  spec's sentiment / backtest / agent layers *around* them. The LSTM output is treated as
  a second signal alongside sentiment; auth guards write/admin endpoints.
- Work phase-by-phase, one PR per subsection, descriptive commits (spec §7).
- Never fabricate metrics; every reported number must be reproducible by a `make` target.

---

## 0. Gap analysis (current repo vs spec)

Legend: ✅ done · 🟡 partial · ❌ missing

### Phase 1 — Engineering foundation
| Item | State | Notes |
|---|---|---|
| Config as `Settings` object | ✅ | `app/core/config.py` is solid. |
| `anthropic_api_key` + trading constants in config | ❌ | Add `anthropic_api_key`; move stop-loss/take-profit/exposure/cash-floor out of code into `Settings`. |
| No raw `os.getenv` sitewide | 🟡 | Confirm via grep; looks clean but verify. |
| `.env.example` documents every var | 🟡 | Exists; must add new vars (anthropic key, trading params, transaction-cost bps, agent flags). |
| Connection pool | ❌ | `app/db/connection.py` opens a fresh `psycopg2.connect()` per call. Move to `ThreadedConnectionPool` (document choice). |
| Versioned migrations | ❌ | Still 4 loose `.sql` files + `init_db.py` concatenation. Introduce numbered-migration runner (or Alembic). Rename `init_db.py` → `migrate.py`. |
| New tables: `articles`, `article_scores`, `trade_attributions`, `agent_reviews`, `backtest_runs` | ❌ | Create all now so later phases have clean migrations. |
| pytest suite (trader math, sell priority, exposure/cash edges, aggregation, API contract) | 🟡 | Only `test_predictor.py`, `test_sentiment_analyzer.py`, one frontend test exist. The spec's priority tests (trader sizing, sell-trigger priority, exposure/cash floors) are absent. |
| DI so DB/yfinance mockable | ❌ | `trader.py` opens its own connection; refactor to accept a cursor/connection — this is the enabling refactor for testability AND for the shared `decide()` in Phase 3. |
| GitHub Actions (ruff, mypy gradual, pytest) + README badge | ❌ | No `.github/workflows/`. |
| Dockerfile multi-stage + compose with separate worker/engine service | 🟡 | `Dockerfile` (single stage) and `docker-compose.yml` exist; compose has postgres/redis/backend/frontend but **no separate engine/worker service**. Engine still runs via `if __name__ == "__main__"`. |
| README rewrite (fix Reddit claim, mermaid, quickstart, disclaimer, limitations) | ❌ | Verify/rewrite. |

### Phase 2 — Sentiment layer v2
| Item | State | Notes |
|---|---|---|
| `SentimentBackend` Protocol (per-text scoring) | ❌ | Today `sentiment_analyzer.calculate_sentiment` returns an aggregate hybrid; FinBERT (`finbert_analyzer.score_headlines`) returns a single mean float. No per-article scores, no pluggable interface. |
| `VaderBackend` / `FinBERTBackend` / `LLMBackend` | 🟡 | VADER + FinBERT logic exists but not behind the interface and not per-article. `LLMBackend` (Claude Haiku few-shot, JSON out, cache on dedup_hash) ❌. |
| Write per-article scores to `article_scores` for all enabled backends | ❌ | Requires `articles` + `article_scores` tables + ingestion rewrite. |
| Aggregation v2 (credibility+recency weighting; confidence from volume × agreement) | ❌ | Current `confidence = min(1, abs(hybrid_score))` — the exact bug spec calls out. |
| `top_drivers` → `trade_attributions` | ❌ | |
| Dedup (normalized-title hash + rapidfuzz > 90) | ❌ | `news.py` returns bare titles, no dedup, no `published_at`/`url`/`source`. Needs richer article ingestion. |
| Eval harness (Financial PhraseBank + hand-labeled golden set; macro-F1, confusion, cost, latency; `make eval-sentiment`; report to `reports/`) | ❌ | The headline resume line. Greenfield. |
| `/trades/{id}/why` endpoint | ❌ | |

### Phase 3 — Backtesting engine
Entirely ❌. Needs: FNSPID subset loader → parquet in `data/` (gitignored) + `make fetch-data`;
pure `decide(signal, position, portfolio_state, params) -> Order | None` shared by live engine
and backtester; event-driven point-in-time loop (news before decision time, next-open fills);
transaction costs at 0/10/25 bps; baselines (equal-weight B&H, SPY B&H, 1000-run random Monte
Carlo percentile); walk-forward splits + trials logging to `backtest_runs`; metrics
(return, CAGR, Sharpe, Sortino, maxDD, Calmar, profit factor, win rate, turnover, exposure);
equity/drawdown PNG to `reports/` + JSON endpoint; `docs/backtesting.md` on bias avoidance;
`make backtest CONFIG=...`.
**Predictor integration risk:** `predict_next_day` trains on a live trailing window ending
"now". To use it point-in-time it needs an `as_of` date param (yfinance history up to that
date only) or must be excluded from backtest decisions. Resolve before wiring it into `decide()`.

### Phase 4 — Agentic analysis layer
Entirely ❌. Bull/Bear/Risk-arbiter gate triggered only for high-stakes orders; hand-rolled
state machine; persist to `agent_reviews` (tokens/latency/cost); fail-open on LLM error;
golden set of 30–50 scenarios; LLM-as-judge groundedness + programmatic JSON/enum checks;
`make eval-agents` + CI grounding threshold; with/without-gate A/B in backtest; `/api/v1/costs`
endpoint + prompt caching. Needs `anthropic_api_key` in config first.

### Phase 5 — Observability, dashboard, deployment
🟡/❌. `structlog` already used across services ✅. Missing: OpenTelemetry spans (ingestion,
each backend score, each agent call, DB ops); `/health` + `/metrics`; kill emoji/debug prints
in service code; 4 focused React views (Portfolio / Signals / Trade log / Research); deploy
config (Railway/Fly/Render + Vercel/Netlify), live demo URL, optional `deploy/k8s/`.

---

## 1. Decisions to confirm before coding

1. **Sell logic regression.** Current `trader.py` has BUY only; the spec's baseline described
   stop-loss/take-profit/bearish-flip SELL logic. Phase 3's shared `decide()` must cover both.
   → Reinstate SELL logic as part of the Phase 1 `trader.py` refactor. Confirm intended.
2. **Migration tooling.** Alembic (needs SQLAlchemy models) vs a simple numbered-SQL runner.
   Recommend the **numbered-SQL runner** — the codebase is raw SQL today; Alembic would force
   an ORM migration that isn't otherwise justified. Document the choice (spec §2.2).
3. **Pool choice.** `psycopg2.pool.ThreadedConnectionPool` (least churn, keeps existing raw SQL)
   vs psycopg3 / SQLAlchemy Core. Recommend **ThreadedConnectionPool**.
4. **Predictor point-in-time.** Add `as_of` to `predict_next_day`/`_build_features` (Phase 3)
   or exclude the LSTM from backtest decisions. Recommend adding `as_of`.
5. **LLM model.** Spec says "Claude Haiku class" for the cheap sentiment/agent calls. Confirm
   `claude-haiku-4-5` for backends and arbiter (load the `claude-api` skill for exact IDs/pricing
   before implementing).

---

## 2. Ordered task breakdown (PR-sized)

### Phase 1 (do first — dependency root)
- **PR 1.1 Config + `.env.example`:** add `anthropic_api_key`, trading params (stop_loss_pct,
  take_profit_pct, exposure_cap, cash_floor, bearish_exit_confidence), transaction-cost bps,
  agent flags. Replace any lingering `os.getenv`. Update `.env.example`.
- **PR 1.2 Connection pool:** `ThreadedConnectionPool` in `connection.py`; keep the
  `get_db_connection()` contextmanager API (getconn/putconn) so callers don't change.
- **PR 1.3 Migrations:** numbered `migrations/00xx_*.sql`; `migrate.py` runner with a
  `schema_migrations` ledger table (idempotent). Fold the 4 existing schemas into `0001`,
  add the 5 new tables in `0002`. Retire `init_db.py`.
- **PR 1.4 Trader refactor + sell logic:** extract decision math into a pure function; make
  `execute_trade_logic` accept a cursor; reinstate stop-loss/take-profit/bearish-flip; add
  exposure cap + cash floor. Sets up the shared `decide()` for Phase 3.
- **PR 1.5 Tests + CI:** pytest for trader sizing, sell-trigger priority, exposure/cash edges,
  sentiment aggregation, one API contract test (mocked cursor). `.github/workflows/ci.yml`
  (ruff + mypy gradual + pytest). README badge.
- **PR 1.6 Docker:** multi-stage `Dockerfile`; add an `engine`/`worker` service to compose with
  its own entrypoint (module `-m app.services.ingestion_engine` or a dedicated `worker.py`).
- **PR 1.7 README rewrite:** fix Reddit→NewsAPI, mermaid architecture, quickstart, disclaimer,
  known-limitations.

### Phase 2
- 2.1 `SentimentBackend` Protocol + refactor VADER/FinBERT to per-article; add `LLMBackend`.
- 2.2 Richer `news.py` ingestion (url/source/published_at) → `articles`; dedup (hash + rapidfuzz).
- 2.3 Aggregation v2 (weighting + real confidence) + `top_drivers` → `trade_attributions`.
- 2.4 Eval harness + `make eval-sentiment` + `reports/` + README table.
- 2.5 `/trades/{id}/why`.

### Phase 3
- 3.1 FNSPID subset loader → parquet + `make fetch-data`.
- 3.2 Shared `decide()`; refactor live engine to call it.
- 3.3 Event-driven backtester (point-in-time, next-open, costs 0/10/25bps).
- 3.4 Baselines + random Monte Carlo percentile + walk-forward + trials logging.
- 3.5 Metrics + equity/drawdown PNG + JSON endpoint + `docs/backtesting.md` + `make backtest`.

### Phase 4
- 4.1 Bull/Bear/Arbiter state machine + `agent_reviews` persistence + fail-open.
- 4.2 Agent eval golden set + LLM-as-judge + `make eval-agents` + CI grounding gate.
- 4.3 A/B with/without gate in backtest; `/api/v1/costs` + prompt caching.

### Phase 5
- 5.1 OTel spans + `/health` + `/metrics`; remove debug prints from service code.
- 5.2 4 React views (Portfolio / Signals / Trade log / Research).
- 5.3 Deploy (Railway/Fly + Vercel), live URL, optional `deploy/k8s/`.

---

## 3. Predictor + auth integration map (standing decision: keep both)
- **LSTM signal:** flows into `decide()` as a secondary gate alongside the sentiment signal
  (as it does today in `execute_trade_logic`). Needs an `as_of` param for point-in-time backtests.
- **Auth:** JWT stays. Public: `/health`, `/metrics`, `/` . Guarded (write/admin/research):
  backtest-run triggers, cost endpoint, any mutation. Decide per-endpoint in Phase 5.

## 4. Suggested first move
Start Phase 1 at PR 1.1–1.3 (config → pool → migrations) since every later phase depends on the
new tables and the pool. Confirm the five decisions in §1, then I'll implement PR-by-PR.
