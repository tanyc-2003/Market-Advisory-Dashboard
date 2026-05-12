# 06 — Developing

## House style

- Python 3.11+, full type hints (no bare `Any`), `from __future__ import annotations` at the top of every module.
- Dataclasses (not dicts) for stable return shapes.
- `structlog.get_logger(__name__)` only — never `print`.
- Named constants for every magic threshold; constants live next to their consumer with a comment when the rationale is non-obvious.
- No mutable default arguments. No global state outside `config/settings.py`.
- All DDL in [src/advisory/data_infra/schema.py](../src/advisory/data_infra/schema.py); no `CREATE TABLE` anywhere else.

## Adding a new layer

Follow the established shape:

1. **Module** at `src/advisory/layerN_<name>/`. Include an `__init__.py` that re-exports the public surface.
2. **Public class / functions** plus typed dataclasses for non-trivial return values.
3. **Audit-log integration** — every method that produces evidence calls `audit_log.record(layer_name, method_name, hyperparams)` *before* doing work so a crash still costs a trial.
4. **Layer 0 sign-off path** — write a `scripts/layer<N>_validation_report.py` that runs the layer's CPCV or walk-forward path, builds a `ValidationReport`, and persists it to `validation_reports`.
5. **Decorator gating** — public methods that produce evidence are wrapped in `requires_production(lambda: report)`. The dashboard renders accordingly.
6. **Tests** at `tests/unit/test_layerN/`. Use the shared fixtures from `tests/conftest.py` (`audit_log`, `synthetic_feature_history`, `feature_cols`, `feature_store`).

## Adding a new feature

1. Add the feature name + lag to [src/advisory/data_infra/lag.py](../src/advisory/data_infra/lag.py).
2. Add its EWMA half-life to `FEATURE_HALFLIVES` in [src/advisory/layer1_market_state/normalizer.py](../src/advisory/layer1_market_state/normalizer.py).
3. If the feature can carry a contradiction signal, add the pair to `CONTRADICTION_PAIRS` in [src/advisory/layer7_hygiene/contradictions.py](../src/advisory/layer7_hygiene/contradictions.py) — note that each new pair is an additional hypothesis test and triggers DSR re-computation.
4. Update the synthetic seed in `scripts/seed_synthetic_data.py` so tests still pass.

## Modifying the validation thresholds

Defaults live in [config/settings.py](../config/settings.py). Override via `.env`. **Do not lower** `coverage_floor` below 0.80 (the constructor raises), `embargo_days` below 504 (the CPCV constructor raises), or `STATIC_TRIAL_FLOOR` below 2000 (no enforcement point yet — keep it as documented invariant).

## Tests

The fixture set in [tests/conftest.py](../tests/conftest.py) provides:

- `audit_log` — in-memory `AuditLog`
- `feature_store` — `FeatureStore` on `tmp_path`
- `synthetic_feature_history` — Polars frame with the 9 features the engines need + a synthetic `hmm_state` column
- `feature_cols` — the 7 default feature names

Property tests use `hypothesis`. CPCV / DSR / Wilson / Kelly all have property tests sweeping random configurations.

Coverage floor is 80% on every layer module. Run:

```powershell
pytest tests/ --cov=src/advisory --cov-report=term-missing
```

## Common pitfalls

- **Long Windows paths.** OneDrive + worktree paths exceed the legacy 260-char limit. `statsmodels.api` import fails (`ImportError: DLL load failed while importing _smoothers_lowess: The filename or extension is too long.`). The project imports `from statsmodels.regression.linear_model import WLS` etc. directly to avoid pulling `statsmodels.graphics` modules. Keep this pattern when adding new statsmodels usage.
- **structlog config.** Don't add `stdlib.add_logger_name` to the processor chain; the native `PrintLogger` has no `.name` attribute. Use `processors.add_log_level` + `TimeStamper` + `ConsoleRenderer`.
- **SHAP array shapes.** SHAP 0.51+ returns `(n_samples, n_features, n_classes)` for binary classifiers. The legacy list-of-arrays shape is also possible. Always normalise to `(n_features,)` for the positive class before indexing into `feature_cols`.
- **Polars `min_periods`.** Renamed to `min_samples` in polars 1.21. Use the new name.
- **DuckDB `np.fill_diagonal` on `corr().to_numpy()`.** The returned array is read-only; wrap with `np.array(..., copy=True)` before `fill_diagonal`.

## CI suggestions

If you wire up CI:

```yaml
- run: pip install -e ".[dev]"
- run: pytest tests/ -v --cov=src/advisory --cov-report=xml
- run: ruff check src/ tests/
- run: mypy src/
```

The full suite takes ~25s on a developer laptop; no network dependencies because the connectors are stubs and the seed is deterministic.

## What's planned

- **Phase 12 — Streamlit dashboard.** Pages for validation status, market state, watchlist, portfolio, sizing, journal, calibration. The components/ folder is sketched in `00_MASTER_PLAN.md` §2.
- **Phase 13 — LLM interpretation.** Strictly optional; sits behind the `LLM_ENABLED` flag in settings. Uses LangChain + Ollama; the LLM never re-runs models, only summarises validated outputs.
- **Phase 14 — Paper-trading operations.** Runs the harness daily for >=180 days before any layer is promoted from `research_preview` to `production`. This is an operational phase, not an implementation phase.
