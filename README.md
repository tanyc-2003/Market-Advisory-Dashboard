# Market Advisory Dashboard

A statistically-disciplined market-intelligence system for a single trader.

The architecture rests on one rule: **no layer output is treated as evidence until Layer 0 has signed it off**. Everything else — historical analogs, regime detection, factor risk, position sizing — is wrapped in that gate. The system is built to make over-confidence harder, not to make trading decisions.

> **What this system does NOT do.** Execute trades. Recommend specific position sizes. Generate deterministic buy/sell signals. Claim predictive certainty. Treat unvalidated outputs as evidence. These restrictions are architectural, not cultural.

---

## Status

| Phase | Layer | Status |
|---|---|---|
| 0a | Survivorship audit | OK |
| 0b | Audit log + backtest counter | OK |
| 0c | Validation substrate (CPCV, WF, DSR, ContinuousValidator) | OK |
| 0d | Paper-trading harness | OK |
| 1 | Bitemporal data infrastructure | OK |
| 2 | Market State Engine (Winsorised HMM) | OK |
| 3 | Historical Analog Engine | OK |
| 4 | Signal Attribution (interventional SHAP) | OK |
| 5 | Hybrid Risk Model (factors + residual PCA) | OK |
| 6 | Portfolio Diagnostics | OK |
| 7 | Market Stress Monitor | OK |
| 8 | Decision Hygiene (contradictions, FDR, confidence, unknowns) | OK |
| 9 | Trader Journal | OK |
| 10 | Trader Calibration System | OK |
| 11 | Position Sizing Diagnostics | OK |
| 12 | Streamlit Dashboard | OK |
| 13 | LLM Interpretation (optional) | OK |

Tests: **188 passing** under Python 3.14.

---

## Quick start

```bash
# Python 3.11+ required; 3.14 is what the project is developed against.
py -3.14 -m venv .venv
.\.venv\Scripts\activate

pip install -e ".[dev]"

python scripts/bootstrap_db.py        # creates main.duckdb + audit.duckdb

# Pick ONE of the two data paths:
python scripts/seed_synthetic_data.py  # deterministic synthetic universe (no network)
# - OR -
python scripts/ingest_real_data.py     # real OHLCV (yfinance) + macro (FRED) - no API key

python scripts/run_validation.py       # populate validation_reports (required before dashboard is useful)

pytest tests/ -v                       # 205 passing

# Run the dashboard (Phase 12)
streamlit run src/advisory/dashboard/app.py
```

> **Why `run_validation.py` is required.** The dashboard reads pre-computed `ValidationReport`s from the `validation_reports` table and refuses to display layer outputs without one — every layer shows `no_report` until you populate it. This is the architectural default: nothing is treated as evidence until Layer 0 has signed it off. Run `python scripts/run_validation.py` after the data step to perform the sign-off pass.

`scripts/seed_synthetic_data.py` is deterministic (seed = 42) and writes both 100 live tickers and 20 synthetic delisted tickers so the survivorship audit can pass on day one.

## Real market data

`scripts/ingest_real_data.py` is the day-one path to running the system on real prices:

| Source | What | Cost |
|---|---|---|
| Yahoo Finance (via `yfinance`) | Daily OHLCV + VIX index | free, no key |
| FRED | Treasury rates (DGS10, DGS2) + ICE BofA HY OAS | free, no key (public CSV endpoint) |

Default universe is the 10 macro factor proxies from the architecture (SPY, TLT, HYG, QQQ, IWD, IWM, UUP, DBC, SVXY, SMH) plus a handful of mega-caps (AAPL, MSFT, NVDA, GOOGL, AMZN). Override with `--tickers`, `--start`, `--end`. Default lookback is 10 years.

By default the script wipes synthetic feature rows (`source = 'synthetic'`) and synthetic delisted entries (`DEL###`) so the validation pipeline averages over real data only. Use `--keep-synthetic-features` or `--keep-synthetic-delisted` to retain them side-by-side.

**A note on survivorship**: free data sources don't provide a clean delisted-tickers feed. Without one, the survivorship audit cannot run against real data, and Layer 0 falls back to `research_preview` for predictive layers (the architecturally correct degradation — the system refuses to claim production sign-off on a universe it can't audit). To get to `production` on real data you'd need either a paid Polygon delisted endpoint, a Sharadar subscription, or to manually populate `delisted_tickers` with a curated list of known historical delistings.

For production-grade fundamentals (earnings revisions, analyst surprise, etc.) you'd plug in Polygon/Sharadar API keys via `.env` — the stub connectors in [src/advisory/data_infra/ingestion.py](src/advisory/data_infra/ingestion.py) document that integration point.

---

## Repository layout

```
src/advisory/
  layer0_validation/    # survivorship - audit log - CPCV - WF - DSR - ValidationReport
  data_infra/           # schema - feature_store - ingestion - lag
  layer1_market_state/  # Winsorised HMM - K-selector - dimensionality
  layer2_analogs/       # Mahalanobis analog engine - conditional expectancy
  layer3_attribution/   # interventional TreeExplainer - factor redundancy
  layer4_risk/          # factor orthogonalisation - EW-OLS - ridge - tail betas - residual PCA
  layer5_stress/        # economic calendar - IntradayFrictionMonitor
  layer6_portfolio/     # position impact preview - two-regime covariance - clustering
  layer7_hygiene/       # validated contradictions - FDR (BY) - confidence language - unknowns
  layer8_journal/       # JournalEntry - JournalStore (DuckDB CRUD)
  layer9_calibration/   # TraderCalibrationSystem (reliability - Brier - ECE - Wilson - thesis-drift)
  layer10_sizing/       # tail-aware Kelly - regime haircut - 20% absolute cap
  layer_llm/            # optional, off-path: LLMContextPacket + CachedLLMInterface
  dashboard/            # Streamlit entry, state helpers, components, 8 pages
  paper_trading/        # RealisticExecutionHarness

config/
  settings.py           # pydantic-settings: paths, validation thresholds, EWMA clip

scripts/
  bootstrap_db.py
  seed_synthetic_data.py

tests/                  # 151 tests across unit + integration
docs/                   # full architecture & usage docs (see docs/01_overview.md)
```

The phase numbering in `Claude code building guide/` is used in commits and tests; the package directory names follow the *layer* numbering from `Advisory_Dashboard_Architecture_v7.md`. Phases 6/7 swap so Layer 5's `vol_z` feeds Layer 2 as a plain float rather than a circular import.

---

## Documentation

The full per-layer documentation lives in [`docs/`](docs/):

- [docs/01_overview.md](docs/01_overview.md) — system purpose and the Layer 0 invariant
- [docs/02_architecture.md](docs/02_architecture.md) — data flow, layer dependencies, sign-off chain
- [docs/03_invariants.md](docs/03_invariants.md) — the seven architectural invariants enforced in code
- [docs/04_layers.md](docs/04_layers.md) — per-layer specifications and public API
- [docs/05_running.md](docs/05_running.md) — bootstrap, seed, test, debug
- [docs/06_developing.md](docs/06_developing.md) — adding a new layer / extending an existing one
- [docs/07_dashboard.md](docs/07_dashboard.md) — Streamlit pages, sign-off gate behaviour, components
- [docs/08_llm.md](docs/08_llm.md) — optional LLM interpretation layer

For background reading, the architecture source-of-truth is `Claude code building guide/Advisory_Dashboard_Architecture_v7.md`. The phase-by-phase build guides are in the same folder.

---

## The seven architectural invariants (enforced in code)

1. **T-1 lag** — `FundamentalRiskModel._aligned_lagged_inputs` asserts the lagged factor frame equals `factor_returns.shift(1)`. Removing the shift fires `AssertionError` immediately.
2. **Winsorisation parity** — `EWMA_CLIP` (default 4.0) is read from `config/settings.py` by both the normaliser and the HMM `winsorize` step.
3. **Interventional SHAP** — `SignalAttributionLayer` constructor raises `ConfigurationError` rather than fall back to path-dependent mode.
4. **FDR method** — `apply_fdr_correction` calls `multipletests(..., method="fdr_by")`. A unit test mocks the call and asserts the kwarg.
5. **Audit floor** — `deflated_sharpe` reads `audit_log.trial_count()` internally; `n_trials = max(audit_count, 2000)` cannot be understated by the caller.
6. **Kelly cap** — `KELLY_ABSOLUTE_CAP = 0.20` clamps every Kelly variant returned by `sizing_diagnostics`.
7. **Adverse fill** — `RealisticExecutionHarness.simulate_fill` asserts buy fills >= ask and sell fills <= bid before returning. Midpoint fills are impossible by construction.

---

## Acknowledgements

The architecture is described in `Claude code building guide/Advisory_Dashboard_Architecture_v7.md` and the phase-by-phase plan is split across the numbered files in the same directory. Both are the source of truth for any disagreement between docs and code.
