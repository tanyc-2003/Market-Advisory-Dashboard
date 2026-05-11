# CLAUDE.md — Advisory Dashboard

## Architecture source
Advisory_Dashboard_Architecture_v7.md (in `Claude code building guide/`)

## Implementation guide
See `Claude code building guide/` — read files in numeric order.

## Core invariant
Layer 0 gates every layer. No layer output is treated as evidence until
its ValidationReport.production_ready == True. The `requires_production`
decorator enforces this in code. Never bypass it.

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
streamlit run src/advisory/dashboard/app.py

## Running tests
pytest tests/ -v --cov=src/advisory

## Linting
ruff check src/ tests/
mypy src/
