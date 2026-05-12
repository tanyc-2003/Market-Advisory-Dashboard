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

## Ingest real market data

Free sources, no API keys:

```powershell
python scripts/ingest_real_data.py
```

Pulls daily OHLCV from Yahoo Finance for the architecture's macro factor proxies (SPY, TLT, HYG, QQQ, IWD, IWM, UUP, DBC, SVXY, SMH) plus five mega-caps (AAPL, MSFT, NVDA, GOOGL, AMZN), the VIX index, and three FRED macro series (DGS10, DGS2, BAMLH0A0HYM2).  Default window is 10 years.

```powershell
python scripts/ingest_real_data.py --tickers SPY AAPL MSFT --start 2020-01-01 --end 2024-12-31
python scripts/ingest_real_data.py --skip-fred             # equity only
python scripts/ingest_real_data.py --keep-synthetic-features  # keep synthetic for A/B
```

Expected output for the default run:

```
[OK] Equity feature rows:  298,770
     VIX feature rows:     2,511
     Macro feature rows:   3,259
     Survivorship audit:   NOT-RUN (coverage 0.000)
     Note: No delisted ticker history present...
```

The survivorship "NOT-RUN" status is **architecturally correct** — free data sources don't provide a delisted-tickers feed, so the audit refuses to make claims it can't verify.  The pipeline will fall back to `research_preview` for predictive layers (not `production`).  To reach `production` on real data, populate `delisted_tickers` from a real source (paid Polygon delisted endpoint or a curated CSV).

## Populate validation reports

```powershell
python scripts/run_validation.py
```

**Run this after seeding.**  The dashboard reads pre-computed `ValidationReport`s from the `validation_reports` table; without this step every layer renders as `no_report` (which is architecturally correct — Layer 0 has not signed anything off yet).

The script performs the full sign-off pass:

1. Survivorship audit on the live + delisted universe.
2. Walk-forward CV for layers with predictive content (`layer1`, `layer2`) using lagged, label-leak-free signal functions.  Deflated Sharpe is computed against the audit log.
3. Diagnostic-baseline reports for the math-only layers (`layer3`–`layer10`).  These land in `research_preview` with a rationale explaining that evidentiary status flows from upstream sign-off and paper trading, not from a CV on the diagnostic layer itself.
4. `layer0` itself is reported `production` when the substrate (audit log + survivorship audit) is operational.

Expected output:

```
Layer                  Status              WF Sharpe   CPCV p30      DSR
------------------------------------------------------------------------
layer0                 production              1.000      0.000    1.000
layer1                 production              3.540      3.233    0.987
layer2                 production              5.305      5.055    1.000
layer3                 research_preview        0.010      0.010    0.000
layer4                 research_preview        0.010      0.010    0.000
...
Persisted 11 ValidationReport(s) to data\db\main.duckdb
```

(Sharpes are inflated because the synthetic data has positive drift; a real-data run would produce more realistic numbers.)  Re-running the script is idempotent — `persist_report` uses `INSERT OR REPLACE`.

## Run the tests

```powershell
pytest tests/ -v
```

Expected result: **188 passed** in ~30s.

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
