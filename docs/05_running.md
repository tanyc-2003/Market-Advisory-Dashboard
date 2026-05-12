# 05 — Running the Project

## Requirements

- **Python 3.11+.** Developed and tested under 3.14.5 on Windows 11.
- ~2 GB free disk for the synthetic feature store after seeding.
- Optional API keys for production data: `POLYGON_API_KEY`, `SHARADAR_API_KEY`, `FRED_API_KEY`. With no keys, the connectors return empty frames (stub mode); the synthetic seed is sufficient for development.

The architecture-canonical dependencies are pinned in `pyproject.toml`. They include polars, duckdb, pyarrow, scikit-learn, hmmlearn, lightgbm, shap, scipy, statsmodels, cvxpy, pydantic-settings, streamlit, plotly, and structlog. The `[dev]` extras add pytest, ruff, mypy, and hypothesis.

## Initial setup

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\activate
pip install --upgrade pip wheel setuptools
pip install -e ".[dev]"
```

The `-e .` installs the project as an editable wheel so the `src/advisory` package is importable from anywhere.

## Bootstrap the databases

```powershell
python scripts/bootstrap_db.py
```

Output:
```
[OK] Main DB schema applied: data\db\main.duckdb
[OK] Audit DB ready: data\db\audit.duckdb
     Current trial count: 0
```

The script is idempotent — running it again is a no-op. It creates:
- `data/db/main.duckdb` with `features_pit`, `delisted_tickers`, `paper_trade_performance`, `validation_reports`, `journal_entries`
- `data/db/audit.duckdb` with `backtest_executions`
- `data/cache/features/` (empty Parquet snapshot dir)

## Seed synthetic data

```powershell
python scripts/seed_synthetic_data.py
```

Output:
```
... survivorship_audit  coverage=1.0 expected_n=20 found_n=20 ... passed=True
[OK] Synthetic data seeded: 3,022,118 feature rows
     Tickers: 120 (100 live + 20 delisted)
     Date range: 2015-05-06 -> 2024-12-31
     Survivorship coverage: 1.000 (passed=True)
```

The seed is deterministic (`SEED = 42`). 11 features are generated per ticker per business day: `ret_1d`, `ret_5d`, `ret_21d`, `realized_vol_21d`, `vix_percentile_63d`, `hy_spread_roc_21d`, `yield_curve_slope`, `earnings_revision_z`, `pct_above_ma50`, `iv_rv_ratio`, `ret_fwd_10d`.

Re-running the script wipes `WHERE source = 'synthetic'` first, so it stays idempotent.

## Run the tests

```powershell
pytest tests/ -v
```

Expected result: **151 passed** in ~25s.

For coverage:
```powershell
pytest tests/ --cov=src/advisory --cov-report=term-missing
```

## Lint and type-check

```powershell
ruff check src/ tests/
mypy src/
```

## Common debugging recipes

### Inspecting the audit log
```python
from src.advisory.layer0_validation.audit_log import AuditLog
log = AuditLog("data/db/audit.duckdb")
print(log.trial_count())
print(log.conn.execute("SELECT * FROM backtest_executions ORDER BY executed_at DESC LIMIT 5").fetchall())
```

### Reading a single feature at a point in time
```python
from datetime import date
from src.advisory.data_infra.feature_store import FeatureStore
fs = FeatureStore("data/db/main.duckdb", "data/cache/features")
print(fs.get_feature_pit("SYN001", "ret_1d", prediction_date=date(2024, 6, 1)))
```

### Building a ValidationReport by hand
```python
from datetime import date
from src.advisory.layer0_validation.report import ValidationReport, validate_layer

r = ValidationReport(
    layer_name="layer1",
    as_of=date.today(),
    walk_forward_sharpe=1.0,
    walk_forward_ece=0.03,
    cpcv_p30_sharpe=0.6,
    deflated_sharpe=0.97,
    survivorship_audit="PASSED",
)
validate_layer(r)
print(r.status, r.rationale)
```

### Verifying the Layer 0 gate behaviour
```python
from src.advisory.layer0_validation.report import requires_production, ValidationGateError

@requires_production(lambda: r)
def my_method():
    return "ok"

try:
    print(my_method())
except ValidationGateError as exc:
    print("blocked:", exc)
```

## Environment variables

Override anything from `config/settings.py` via a `.env` file at the project root. See `.env.example` for the full list. Notable knobs:

- `WF_SHARPE_FLOOR` (default 0.5) — Layer 0 sign-off threshold
- `DSR_FLOOR` (default 0.95) — Deflated Sharpe sign-off threshold
- `EWMA_CLIP` (default 4.0) — shared Winsorisation boundary
- `STATIC_TRIAL_FLOOR` (default 2000) — `n_trials` floor for the DSR
- `LLM_ENABLED` (default false) — kept off-path until Phase 13
