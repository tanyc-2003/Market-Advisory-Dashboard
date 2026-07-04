# Market Advisory Dashboard

A statistically-disciplined market-intelligence system for a single trader.

## What this is

A local-first dashboard that turns market data into *honest evidence about evidence*.  You point it at a universe of tickers; it tells you:

- **Where the market is now** — regime detection via a Winsorised Hidden Markov Model + a transition-signal banner when the model is uncertain.
- **What history says** — a Mahalanobis historical-analog engine that surfaces the top-K most similar past states, their forward-return distribution, and their hit rate.
- **What's driving each name** — interventional SHAP attribution per asset, with the background dataset's vintage date displayed alongside.
- **What you'd be adding** — pre-trade portfolio impact preview, two-regime covariance, named stress scenarios, and correlation clustering.
- **What you're calibrated for** — a journal-fed reliability diagram with Brier score, ECE, and a thesis-drift detector.
- **What you'd size into** — tail-aware Kelly diagnostics with a 20% absolute cap, regime-uncertainty haircut, and explicit fragility warnings.

It also **grades itself and its inputs**, and keeps an auditable memory (Tier 1–3 enhancement sections — see [docs/11_dashboard_sections.md](docs/11_dashboard_sections.md)):

- **How its own calls have done** — a self-grading track record that logs each watchlist call *as stated* and resolves it against the realised forward return (rolling hit rate, alpha vs SPY, reliability curve).
- **Whether the inputs are fresh** — a per-feed data-health / PIT-staleness monitor that grades the *inputs* the way Layer 0 grades outputs.
- **The case for and against** — a bull/bear synthesis composed from signals already computed, plus a 0–100 heuristic market-stress gauge (weights shown, never dressed as a model).
- **What changed and why** — a "trading-as-git" decision change-log with rationale, and a persistent per-ticker notes inbox.
- **A second, gated forecast** — the Kronos probabilistic forecaster feeding the watchlist fan, **hidden until it passes Layer 0** (it currently does not — see [docs/kronos_finetune.md](docs/kronos_finetune.md)).
- **What the field is publishing** — an arXiv research radar tracking the methods this system uses.

Every output is wrapped in one rule: **no layer's result is treated as evidence until Layer 0 has signed it off.**  The dashboard refuses to render layer outputs without a passing `ValidationReport` — a positive walk-forward Sharpe alone isn't enough; the Deflated Sharpe Ratio applies a trial-count penalty drawn from a monotonic DuckDB audit log so nobody can pretend they ran fewer experiments than they did.

> **What this system does NOT do.** Execute trades. Recommend specific position sizes. Generate deterministic buy/sell signals. Claim predictive certainty. Treat unvalidated outputs as evidence. These restrictions are architectural, not cultural.

The system is designed to make over-confidence harder — not to make trading decisions.

---

## Quick start

```bash
# Python 3.11+ required; 3.14 is what the project is developed against.
py -3.14 -m venv .venv
.\.venv\Scripts\activate

pip install -e ".[dev]"

# Optional: copy the example .env and edit it
cp .env.example .env

python scripts/bootstrap_db.py        # creates main.duckdb + audit.duckdb

# Pick ONE of the two data paths:
python scripts/seed_synthetic_data.py  # deterministic synthetic universe (no network)
# - OR -
python scripts/ingest_real_data.py     # real OHLCV (yfinance) + macro (FRED) - no API key

python scripts/run_validation.py       # populate validation_reports (required before the Streamlit gate renders)

# Run the UI — pick one:

# (A) React web app (current UI) — needs Node 18+ and the API extra
pip install -e ".[api]"
python scripts/run_api.py              # FastAPI on http://localhost:8000
#   ...then in a second terminal:
cd frontend && npm install && npm run dev   # Vite dev server on http://localhost:5173

# (B) Streamlit (legacy UI)
streamlit run src/advisory/dashboard/app.py
```

There are **two UIs over the same backend** (see [docs/10_web_stack.md](docs/10_web_stack.md)):

- **React web app (current):** open `http://localhost:5173`. It loads the whole dashboard from `GET /api/dashboard` in one round trip. With no data present it renders representative values (the sidebar says so); run the data pipeline below to make the market-state, watchlist, sizing and calibration panels live, each with an honest research-preview disclosure.
- **Streamlit (legacy):** open `http://localhost:8501`. The first page is **Validation** — every other page is gated on the sign-off shown there.

> **Why `run_validation.py` is required.** The dashboard reads pre-computed `ValidationReport`s from the `validation_reports` table and refuses to display layer outputs without one — every layer shows `no_report` until you populate it. This is the architectural default: nothing is treated as evidence until Layer 0 has signed it off.

---

## Configuration

All knobs flow through `.env` (copy from `.env.example`).  The system reads them through a single `pydantic-settings` object in [`config/settings.py`](config/settings.py), so changing a value in `.env` and restarting Streamlit is enough to pick it up — no code edit needed.

### Mode selection

| Env var | Values | Default | What it does |
|---|---|---|---|
| `APP_MODE` | `v7_lite` · `v7_institutional` | `v7_lite` | Picks the data tier and which layers are active. |

The three operating modes:

| Mode | Data | Layers active | UI |
|---|---|---|---|
| `APP_MODE=v7_lite` | yfinance · FRED · CBOE *(all free, no key)* | All except Layers 3 + 4 | Survivorship-bias panel on every analog-distribution page; locked tiles for Layers 3 + 4 |
| `APP_MODE=v7_institutional` with paid keys | Polygon · Sharadar · FRED · CBOE | All | Full layer set; no bias panels |
| `APP_MODE=v7_institutional` without paid keys | Synthetic only | All | Red **Developer Mode** banner; exercisable without subscriptions |

Restart Streamlit after changing the mode.

### Data sources & API keys

All paid keys are optional — leave them blank to stay in lite / developer mode.

| Env var | When you need it |
|---|---|
| `POLYGON_API_KEY` | V7 Institutional OHLCV + 1-min bars + delisted ticker history. |
| `SHARADAR_API_KEY` | V7 Institutional fundamentals (earnings revisions, analyst surprise, etc.). |
| `FRED_API_KEY` | Optional; the free CSV endpoint is used by default. Set this if you want to switch to the rate-limited authenticated API. |

### Database paths

| Env var | Default | Purpose |
|---|---|---|
| `MAIN_DB_PATH` | `data/db/main.duckdb` | Feature store, journal, validation reports, LLM cache. |
| `AUDIT_DB_PATH` | `data/db/audit.duckdb` | Monotonic backtest-execution counter (powers the Deflated Sharpe trial floor). |
| `CACHE_DIR` | `data/cache/features` | Parquet snapshot cache. |

### Validation thresholds

These define the Layer 0 sign-off gate.  Defaults are architecture-pinned; lower them only with a clear reason.

| Env var | Default | Meaning |
|---|---|---|
| `WF_SHARPE_FLOOR` | `0.5` | Walk-forward Sharpe must clear this to pass. |
| `WF_ECE_CEILING` | `0.05` | Walk-forward Expected Calibration Error must be ≤ this. |
| `CPCV_P30_FLOOR` | `0.0` | 30th-percentile CPCV Sharpe must clear this (worst-path bar). |
| `DSR_FLOOR` | `0.95` | Deflated Sharpe Ratio must clear this for `production` status. |
| `STATIC_TRIAL_FLOOR` | `2000` | `n_trials = max(audit_count, this)` — caller cannot understate it. |
| `DIVERGENCE_THRESHOLD` | `0.30` | V7 Institutional paper-trade vs backtest Sharpe divergence threshold. |
| `DIVERGENCE_THRESHOLD_LITE` | `0.40` | V7_lite version (more permissive given noisier data). |
| `MAX_MISSING_BAR_FRACTION` | `0.02` | Lite mode pauses validation if missing-bar fraction exceeds this. |
| `MAX_STALE_CROSS_TICKER_FRACTION` | `0.20` | Lite mode pauses validation if cross-ticker staleness exceeds this. |

### Feature engineering

| Env var | Default | Purpose |
|---|---|---|
| `UNIVERSE_SIZE` | `100` | Default ticker count for the synthetic seed. |
| `EWMA_CLIP` | `4.0` | Winsorisation σ-cap shared between the EWMA normaliser and the HMM. |

### Sizing diagnostics

| Env var | Default | Purpose |
|---|---|---|
| `KELLY_ABSOLUTE_CAP` | `0.20` | Hard cap on every Kelly variant returned by `sizing_diagnostics`. **Invariant**: outputs never exceed this. |
| `ANNUAL_IMPAIRMENT_RATE` | `0.02` | V7_lite — probability per analog of a synthetic wipeout draw. |
| `SYNTHETIC_WIPEOUT_RETURN` | `-0.60` | V7_lite — magnitude of an injected wipeout return. |

### Optional LLM

The LLM page (Page 8) is hidden unless explicitly enabled.

| Env var | Default | Purpose |
|---|---|---|
| `LLM_ENABLED` | `false` | Toggle the optional LLM interpretation page. |
| `LLM_MODEL` | `llama3` | Local Ollama model name. |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Where to reach Ollama. |

### Typical operator workflows

```bash
# Run lite with free data (default — no .env edit needed)
python scripts/ingest_real_data.py
python scripts/run_validation.py
streamlit run src/advisory/dashboard/app.py
```

```bash
# Run institutional with synthetic data (Developer Mode — no API keys)
echo "APP_MODE=v7_institutional" >> .env
python scripts/seed_synthetic_data.py
python scripts/run_validation.py
streamlit run src/advisory/dashboard/app.py
```

```bash
# Run institutional with live paid data
echo "APP_MODE=v7_institutional" >> .env
echo "POLYGON_API_KEY=..." >> .env
echo "SHARADAR_API_KEY=..." >> .env
# Production ingest script goes here (paid integration is documented in
# src/advisory/data_infra/ingestion.py)
python scripts/run_validation.py
streamlit run src/advisory/dashboard/app.py
```

### Real-data quick reference

`scripts/ingest_real_data.py` runs against free sources:

| Source | What | Cost |
|---|---|---|
| Yahoo Finance (via `yfinance`) | Daily OHLCV + VIX index | free, no key |
| FRED | Treasury rates (DGS10, DGS2) + ICE BofA HY OAS | free, no key (public CSV endpoint) |

Default universe is the 10 macro factor proxies from the architecture (SPY, TLT, HYG, QQQ, IWD, IWM, UUP, DBC, SVXY, SMH) plus a handful of mega-caps (AAPL, MSFT, NVDA, GOOGL, AMZN).  Override with `--tickers`, `--start`, `--end`.  Default lookback is 10 years.

**Note on survivorship**: free data sources don't provide a clean delisted-tickers feed.  Without one, the survivorship audit cannot run against real data, and Layer 0 falls back to `research_preview` — the architecturally correct degradation.  Production sign-off needs either a paid Polygon delisted endpoint, a Sharadar subscription, or a manually-curated `delisted_tickers` table.

---

## Repository layout

```
src/advisory/
  layer0_validation/    # survivorship - audit log - CPCV - WF - DSR - ValidationReport
  data_infra/           # schema - feature_store - ingestion - lag
                        # + yfinance, FRED PIT-safe, CBOE adapters
                        # + 9-dim feature pipeline (feature_pipeline_lite.py)
  layer1_market_state/  # Winsorised HMM - K-selector - dimensionality
                        # + model registry (V7_lite: registry.py)
  layer2_analogs/       # Mahalanobis analog engine - conditional expectancy
                        # V7_lite: feature_quality_note in DisagreementResult
  layer3_attribution/   # interventional TreeExplainer - factor redundancy
                        # V7_lite: returns {"status": "LOCKED"}
  layer4_risk/          # factor orthogonalisation - EW-OLS - ridge - tail betas
                        # V7_lite: returns {"status": "LOCKED"}
  layer5_stress/        # economic calendar - IntradayFrictionMonitor
                        # V7_lite: LiteFrictionMonitor (Amihud + Corwin-Schultz)
  layer6_portfolio/     # position impact preview - two-regime covariance - clustering
  layer7_hygiene/       # validated contradictions - FDR (BY) - confidence - unknowns
                        # V7_lite: UNTESTABLE_LITE branch on contradictions
  layer8_journal/       # JournalEntry - JournalStore (DuckDB CRUD)
  layer9_calibration/   # TraderCalibrationSystem (reliability, Brier, ECE, Wilson)
  layer10_sizing/       # tail-aware Kelly - regime haircut - 20% absolute cap
                        # V7_lite: lite_diagnostics.py adds binomial wipeout injection
  layer_kronos/         # probabilistic forecaster (validated-only, Tier 3 #9)
                        # forecaster.py (block-bootstrap) + transformer.py (pretrained
                        # Kronos) + finetune.py + vendored kronos_vendor/
  layer_llm/            # optional, off-path: LLMContextPacket + CachedLLMInterface
  api/                  # FastAPI service for the React UI (current)
                        # app, live (payload assembly), presentation (representative
                        # data), db; live wiring: market_state_live, analogs_live,
                        # calibration_live, kronos_forecast_live, stress_live,
                        # track_record_live, data_health_live, recommendation_log,
                        # notes_live, synthesis_live, research_radar_live
  dashboard/            # Streamlit entry, state helpers, components, 8 pages (legacy UI)
                        # V7_lite: mode indicator, survivorship panel, locked tiles
  paper_trading/        # RealisticExecutionHarness
                        # V7_lite: CS-spread / amihud_z separation assertion

frontend/               # React + Vite + TypeScript SPA (current UI)
                        # src/api.ts (typed client), App.tsx, views/, components/
config/                 # settings.py + sector_map.yaml + lite_feature_set_9dim.yaml
scripts/                # bootstrap_db, seed_synthetic_data, ingest_real_data,
                        # run_validation, train_hmm, validate_hmm_candidate, run_api;
                        # Kronos: train_kronos, validate_kronos_candidate,
                        # kronos_forecast, finetune_kronos;
                        # enhancement refresh: track_record, snapshot_recommendations,
                        # research_radar
brainstorm/             # feature roadmap + Tier 1-3 specs + frontend display spec
tests/                  # 280 passing tests (V7 + V7_lite + enhancement sections)
docs/                   # full architecture & usage docs
```

The phase numbering in `Claude code building guide/` is used in commits and tests; the package directory names follow the *layer* numbering from `Advisory_Dashboard_Architecture_v7.md`.  Phases 6/7 swap so Layer 5's `vol_z` feeds Layer 2 as a plain float rather than a circular import.

---

## Documentation

The full per-layer documentation lives in [`docs/`](docs/):

- [docs/01_overview.md](docs/01_overview.md) — system purpose and the Layer 0 invariant
- [docs/02_architecture.md](docs/02_architecture.md) — data flow, layer dependencies, sign-off chain
- [docs/03_invariants.md](docs/03_invariants.md) — the seven architectural invariants enforced in code
- [docs/04_layers.md](docs/04_layers.md) — per-layer specifications and public API
- [docs/05_running.md](docs/05_running.md) — bootstrap, seed, test, debug
- [docs/06_developing.md](docs/06_developing.md) — adding a new layer / extending an existing one
- [docs/07_dashboard.md](docs/07_dashboard.md) — Streamlit pages (legacy UI), sign-off gate behaviour, components
- [docs/08_llm.md](docs/08_llm.md) — optional LLM interpretation layer
- [docs/09_v7_lite.md](docs/09_v7_lite.md) — V7_lite (Scanner+) extension and operating modes
- [docs/10_web_stack.md](docs/10_web_stack.md) — **React frontend + FastAPI API** (current UI): payload contract, live-vs-representative wiring, the data pipeline
- [docs/11_dashboard_sections.md](docs/11_dashboard_sections.md) — the nine Tier 1–3 enhancement sections (track record, data health, forecast, synthesis, change-log, notes, stress, radar, Kronos): module, payload key, and gate for each
- [docs/kronos_finetune.md](docs/kronos_finetune.md) — Kronos forecaster: fine-tune pipeline, GPU recipe, and the empirical gate result

The enhancement-section roadmap (selection criteria, source repos, licensing) lives in [brainstorm/feature-roadmap.md](brainstorm/feature-roadmap.md) with per-tier specs alongside it.

For background reading, the architecture source-of-truth is `Claude code building guide/Advisory_Dashboard_Architecture_v7.md` (and `_v7_lite.md` for the extension).  The phase-by-phase build guides are in the same folder.

---

## The seven architectural invariants (enforced in code)

1. **T-1 lag** — `FundamentalRiskModel._aligned_lagged_inputs` asserts the lagged factor frame equals `factor_returns.shift(1)`.  Removing the shift fires `AssertionError` immediately.
2. **Winsorisation parity** — `EWMA_CLIP` (default 4.0) is read from `config/settings.py` by both the normaliser and the HMM `winsorize` step.
3. **Interventional SHAP** — `SignalAttributionLayer` constructor raises `ConfigurationError` rather than fall back to path-dependent mode.
4. **FDR method** — `apply_fdr_correction` calls `multipletests(..., method="fdr_by")`.  A unit test mocks the call and asserts the kwarg.
5. **Audit floor** — `deflated_sharpe` reads `audit_log.trial_count()` internally; `n_trials = max(audit_count, 2000)` cannot be understated by the caller.
6. **Kelly cap** — `KELLY_ABSOLUTE_CAP = 0.20` clamps every Kelly variant returned by `sizing_diagnostics`.
7. **Adverse fill** — `RealisticExecutionHarness.simulate_fill` asserts buy fills ≥ ask and sell fills ≤ bid before returning.  Midpoint fills are impossible by construction.

V7_lite adds eight more invariants — see [docs/09_v7_lite.md](docs/09_v7_lite.md).

---

## Acknowledgements

The architecture is described in `Claude code building guide/Advisory_Dashboard_Architecture_v7.md` and the phase-by-phase plan is split across the numbered files in the same directory.  Both are the source of truth for any disagreement between docs and code.
