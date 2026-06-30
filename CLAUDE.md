# CLAUDE.md — Advisory Dashboard

## Architecture sources
- V7 Institutional: `Claude code building guide/Advisory_Dashboard_Architecture_v7.md`
- V7_lite (Scanner+): `Claude code building guide/Advisory_Dashboard_Architecture_v7_lite.md`

## Implementation guide
See `Claude code building guide/` — read files in numeric order.
V7 phases: `00`-`08`.  V7_lite extension: `09`-`12`.

## Mode switching
Set `APP_MODE=v7_lite` in `.env` (default) for free data sources.
Set `APP_MODE=v7_institutional` to restore the full layer set (requires
Polygon + Sharadar keys; without them the system surfaces a
**Developer Mode** banner and reads synthetic data).

## Core invariant
Layer 0 gates every layer. No layer output is treated as evidence until
its ValidationReport.production_ready == True. The `requires_production`
decorator enforces this in code. Never bypass it.

## V7_lite invariants — never violate these
1. No V7 Institutional code is deleted. All lite-mode changes are additive.
2. Every output affected by survivorship bias carries a disclosure. Silent
   degradation is forbidden.
3. `amihud_z` feeds Layer 5 stress detection; `cs_spread_execution_proxy`
   feeds the realistic execution harness. Never substitute.
4. `SURVIVORSHIP_WIN_RATE_ADJUSTMENT` does NOT exist. The correct fix is
   binomial wipeout injection into ES_5.
5. HY/IG OAS credit spreads are Layer 1 Macro features — never Layer 5
   stress signals.
6. FRED fetches in V7_lite use `fetch_fred_pit_safe()` with the vintage API.
7. Layer 3 and Layer 4 are locked in V7_lite. They return
   `{"status": "LOCKED"}` — they do not crash.

## Critical correctness properties
1. T-1 lag: factor returns at date T use `knowledge_date < T`. The `.shift(1)`
   assertion in `FundamentalRiskModel._aligned_lagged_inputs()` must never be
   removed.
2. Winsorisation: HMM training and inference use the same `sigma_cap=4.0`.
3. SHAP mode: always `feature_perturbation="interventional"`.
4. FDR: always `method="fdr_by"` (Benjamini-Yekutieli).
5. Kelly cap: `KELLY_ABSOLUTE_CAP = 0.20`.
6. Audit floor: `STATIC_TRIAL_FLOOR = 2000`. `n_trials = max(audit_count, 2000)`.
7. Fill model: paper trading always fills at the adverse side of the spread.

## Running the project
pip install -e ".[dev]"
python scripts/bootstrap_db.py
python scripts/seed_synthetic_data.py
streamlit run src/advisory/dashboard/app.py   # legacy Streamlit UI

## Web UI (current) — React + Vite frontend + FastAPI API
# Architecture + live-vs-representative wiring: docs/10_web_stack.md
pip install -e ".[api]"
python scripts/run_api.py                      # FastAPI on :8000
cd frontend && npm install && npm run dev      # Vite on :5173
# Make live panels real: scripts/ingest_real_data.py then scripts/train_hmm.py --mode v7_lite
# API code: src/advisory/api/ (presentation.py = representative source of truth;
# *_live.py = live wiring with research-preview disclosures).

## Running tests
pytest tests/ -v --cov=src/advisory

## Linting
ruff check src/ tests/
mypy src/
