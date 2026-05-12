# 04 — Layers

A reference for every public class / function exposed by `src/advisory/`. Each subsection lists the module, the key public surface, and the architectural contract.

---

## Layer 0 — Validation substrate

Module: [src/advisory/layer0_validation/](../src/advisory/layer0_validation/)

| Symbol | Type | Contract |
|---|---|---|
| `SurvivorshipAuditor(coverage_floor=0.95)` | class | `audit(live, delisted, start, end) -> dict`. Floor cannot be set below 0.80 (raises `ValueError`). |
| `SurvivorshipAuditError` | exception | Raised by `raise_if_failed` when audit fails — blocks downstream validation. |
| `AuditLog(db_path)` | class | Append-only DuckDB; `record(layer, fn, hyperparams)` returns the new trial count; `trial_count()` is the row count. |
| `ValidationReport` | dataclass | Carries WF Sharpe / ECE / CPCV p30 / DSR / survivorship. `.status` -> `"production"` / `"research_preview"` / `"blocked"`. `.to_dashboard_dict()` is JSON-safe. |
| `validate_layer(report) -> str` | fn | Mutates `report.production_ready` + `report.rationale`. Returns the status. |
| `requires_production(get_report)` | decorator | Wraps a method; raises `ValidationGateError` if the report is not production-ready. |
| `CPCVRunner` | class | Combinatorial purged CV with 504-day embargo floor + horizon-purging. `run()` records to audit log before fitting. Falls back to WF when history is short. |
| `WalkForwardCV` | class | Strict expanding-window walk-forward CV. `run()` returns the same shape as CPCV. |
| `deflated_sharpe(sharpe, skew, kurt, n_obs, audit_log)` | fn | Reads `audit_log.trial_count()` internally. Returns `{deflated_sharpe, expected_max_under_null, n_trials_used, ...}`. |
| `ContinuousValidator` | class | `evaluate(layer, pre_deployment_sharpe, paper_trade_log)` returns demote-yes/no after >= 90 days; threshold 30% relative divergence. |

---

## Data infrastructure

Module: [src/advisory/data_infra/](../src/advisory/data_infra/)

| Symbol | Contract |
|---|---|
| `bootstrap_schema(conn)` | Creates `features_pit`, `delisted_tickers`, `paper_trade_performance`, `backtest_executions`, `validation_reports`, `journal_entries`. Idempotent. |
| `PIT_QUERY` | The point-in-time SQL constant; uses `knowledge_date < ?` (strict less-than). |
| `FUNDAMENTAL_LAGS` + `get_lag(name)` | Knowledge-date lag in trading days per feature. Unknown features default to 1 (conservative). |
| `FeatureStore(db_path, cache_dir)` | The only read path for features. `get_feature_pit`, `get_feature_history` (lag-aware), `write_features`, `cache_snapshot`, `load_snapshot`. |
| `trading_days_before(anchor, n)` | Weekend-skipping helper used by the lag arithmetic. |
| Ingestion connectors | Stub `PolygonConnector`, `SharadarConnector`, `FREDConnector`, `CBOEConnector` with injectable HTTP clients. |

---

## Layer 1 — Market State Engine

Module: [src/advisory/layer1_market_state/](../src/advisory/layer1_market_state/)

| Symbol | Contract |
|---|---|
| `FEATURE_HALFLIVES` | Per-feature EWMA half-life in trading days (5 to 126). |
| `EWMA_CLIP` | The shared Winsorisation boundary, sourced from `config/settings.py`. |
| `ewma_normalize(values, half_life)` | EWMA z-score clipped to `[-EWMA_CLIP, EWMA_CLIP]`. |
| `winsorize(arr, sigma_cap)` | Column-wise σ clip; pairs with `MarketStateEngine.attach_training_moments`. |
| `MarketStateEngine` | Predictor-only HMM wrapper. `get_current_state(features) -> StateObservation` (probs, dominant id, uncertainty, transition signal). `decode_path` runs Viterbi over history. |
| `train_market_state_engine(...)` | Factory: fits Gaussian HMM, attaches training mean/std, returns the engine. Records to audit log. |
| `select_k_oos(history, cols, candidate_ks, audit_log)` | Strict chronological 80/20 split, picks the K with the highest test log-likelihood. |
| `dimensionality_adequacy(X, warn_callback)` | OOS R² test against the dominant variance direction; floor 0.40. |

---

## Layer 2 — Historical Analog Engine

Module: [src/advisory/layer2_analogs/](../src/advisory/layer2_analogs/)

| Symbol | Contract |
|---|---|
| `HistoricalAnalogEngine(feature_cols, friction_monitor=None)` | The friction monitor is optional; when set + a ticker is passed, `vol_z` is read from `monitor.get_vol_z(ticker)`. |
| `find_analogs(history, query, anchor_date, k, min_separation, state_filter, vol_z, ticker)` | Mahalanobis top-K with MCD fallback to Ledoit-Wolf. `min_separation` floor is 5. Returns `AnalogResult`. |
| `find_analogs_with_disagreement(...)` | Two passes (global vs within-state); returns overlap_pct and the architecture-pinned disagreement note. |
| `build_conditional_expectancy_table(history)` | Forward-return stats bucketed into five named regimes ("Calm bull" … "Stressed bear"). |

`AnalogResult` carries `effective_n_recency_weighted` (5-year half-life weighting), `covariance_method` (`mcd` or `ledoit_wolf`), and `hit_rate`.

---

## Layer 3 — Signal Attribution (SHAP)

Module: [src/advisory/layer3_attribution/](../src/advisory/layer3_attribution/)

| Symbol | Contract |
|---|---|
| `SignalAttributionLayer(model, feature_cols, background_provider, today)` | Constructor raises `TypeError` if `model` lacks `predict_proba`. Raises `ConfigurationError` if interventional explainer cannot be built. |
| `explain_asset(features, ticker, as_of)` | Returns `background_vintage` (ISO), top 3 features, all contributions, `tight_top_margin` flag. Refreshes background after 5 calendar days. |
| `calibrate_model(model, X, y)` | Isotonic `CalibratedClassifierCV(method="isotonic", cv="prefit")`. Logs ECE. |
| `detect_factor_redundancy(asset_attributions)` | Watchlist-level dominance check; warning fires at >= 50%. |

---

## Layer 4 — Hybrid Risk Model

Module: [src/advisory/layer4_risk/](../src/advisory/layer4_risk/)

| Symbol | Contract |
|---|---|
| `MACRO_FACTOR_PROXIES` | 10 factor names -> ETF proxy tickers (SPY, TLT, HYG, QQQ, IWD, IWM, UUP, DBC, SVXY, SMH). |
| `FACTOR_ORDER` | Iteration order for `orthogonalize_factors`. Stable; never sorted or shuffled. |
| `orthogonalize_factors(returns)` | Sequential residualisation in `FACTOR_ORDER`. First factor unchanged. Zero-variance factors pass through with a warning. |
| `FundamentalRiskModel(audit_log)` | Three methods, all T-1 lagged with the assertion: `fit_ew_ols(λ=0.97)`, `fit_ridge(α)`, `fit_tail_betas(lookback=504)`. |
| `AssetExposureResult` | Typed dataclass for cross-layer consumption. |
| `ResidualFactorAnomalyDetector(n_components=3, bootstrap_n=100, seed=42)` | Bootstrap-stable hidden clusters; Jaccard 0.70, stability 0.80, min 3 tickers. |

---

## Layer 5 — Market Stress Monitor

Module: [src/advisory/layer5_stress/](../src/advisory/layer5_stress/)

| Symbol | Contract |
|---|---|
| `CalendarEvent` (enum) | `fomc_day`, `cpi_day`, `nfp_day`, `gdp_day`, `options_expiry`, `quarter_end`. |
| `SUPPRESSION_RULES` | Per-event suppression message; consumed by `is_suppression_active`. |
| `is_suppression_active(date, calendar)` | Returns `(bool, reason)`. Empty calendar -> never suppressed. |
| `load_economic_calendar(path)` | Loads JSON `{"YYYY-MM-DD": ["fomc_day", ...]}`. |
| `IntradayFrictionMonitor(economic_calendar)` | `compute_friction_z_score(...)` returns z-scores per channel + alert bool; calendar-suppressed days return `{"status": "SUPPRESSED"}`. |
| `get_vol_z(ticker)` | Cached value for Layer 2 wiring. |

---

## Layer 6 — Portfolio Diagnostics

Module: [src/advisory/layer6_portfolio/](../src/advisory/layer6_portfolio/)

| Symbol | Contract |
|---|---|
| `preview_position_impact(...)` | Returns `PositionImpactResult` (dataclass) with vol_before/after, factor_additions, effective_n change. Empty portfolio handled. Unknown ticker -> `error` field. Asserts weight sum invariant. |
| `CRISIS_WINDOWS` | Architecture-pinned crisis date ranges (2008, 2011, 2020, 2022). |
| `fit_two_regime_covariance(returns)` | MCD with Ledoit-Wolf fallback. Both PSD. |
| `STRESS_SCENARIOS` | Named scenarios with per-factor σ shocks. `list_scenarios()` returns names. |
| `run_stress_test(name, weights, betas, cov_dict)` | Returns `factor_impact`, `stressed_vol`, and the exact `STRESS_NOTE` string. |
| `detect_correlation_clusters(returns, weights)` | Threshold 0.75; carries `CLUSTER_WARNING_TEXT` ("These positions behave as a single trade."). |

---

## Layer 7 — Decision Hygiene

Module: [src/advisory/layer7_hygiene/](../src/advisory/layer7_hygiene/)

| Symbol | Contract |
|---|---|
| `CONTRADICTION_PAIRS` | Four developer-specified pairs; fixed by architecture. |
| `find_validated_contradictions(history)` | Fisher's exact at p<0.01, min 20 in each cell. Output `label` is the exact architecture string. |
| `apply_fdr_correction(alerts)` | `multipletests(method="fdr_by")` only. |
| `SEVERITY_SCORES` | Per-alert-type integer scores 1-3. |
| `filter_top_k_alerts(alerts, k)` | Severity-desc, then corrected-p-asc. |
| `CONFIDENCE_LANGUAGE` + `get_confidence_language(n, hit_rate, ci_low)` | Tier templates: insufficient / weak / moderate / strong. |
| `generate_unknowns_section(...)` | Returns a list of strings; `STRUCTURAL_CHANGE_UNKNOWN` is always last. |

---

## Layer 8 — Trader Journal

Module: [src/advisory/layer8_journal/](../src/advisory/layer8_journal/)

| Symbol | Contract |
|---|---|
| `JournalEntry` | Dataclass; `validate()` enforces direction ∈ {long, short, avoided}, confidence ∈ [1, 5], horizon > 0, non-blank thesis. `is_complete` checks exit fields. |
| `JournalStore(conn)` | `save`, `close_trade`, `get_open_trades`, `get_completed_trades`, `get_all`, `as_polars`. |
| `journal_entries` table | 18 columns; JSON `contradictions` field. |

---

## Layer 9 — Calibration

Module: [src/advisory/layer9_calibration/](../src/advisory/layer9_calibration/)

| Symbol | Contract |
|---|---|
| `TraderCalibrationSystem` | `evaluate(journal)` returns reliability table per confidence level, Brier, ECE, calibration band. Min 15 entries. |
| `CONFIDENCE_TO_PROB` | Confidence 1-5 -> implied probability {0.30, 0.45, 0.55, 0.70, 0.85}. |
| `_wilson_score(wins, n)` | Wilson 95% CI; `n=0` returns `(0.0, 1.0)`. |
| `compute_regime_performance(journal)` | Skips null `market_state_id` with warning. |
| `detect_thesis_drift(journal)` | Flags > 3 invalidated-and-lost trades. |

---

## Layer 10 — Position Sizing Diagnostics

Module: [src/advisory/layer10_sizing/](../src/advisory/layer10_sizing/)

| Symbol | Contract |
|---|---|
| `sizing_diagnostics(returns, state_uncertainty, overlap_pct, base_haircut=0.5)` | Returns `raw_kelly`, `haircut_kelly_standard`, `haircut_kelly_regime`, `displayed_kelly`, all clamped to [0, 0.20]. |
| `KELLY_ABSOLUTE_CAP = 0.20` | Hard cap on every output. |
| `KELLY_LOW_SAMPLE_THRESHOLD = 100` | Triggers a fragility warning. |
| `ES_QUANTILE = 0.05` | 5th-percentile expected-shortfall as the Kelly loss term. |
| `SIZING_NOTE` | Exact architecture string surfaced on the dashboard. |

---

## Paper trading

Module: [src/advisory/paper_trading/](../src/advisory/paper_trading/)

| Symbol | Contract |
|---|---|
| `RealisticExecutionHarness` | `simulate_fill(direction, bid, ask, order_size, adv, vol_z, spread_z)` returns `FillResult`. Buys >= ask, sells <= bid. `simulate_vwap_execution(...)` slices an order across intraday bars. |
| `SQRT_IMPACT_K = 0.1`, `FRICTION_LAMBDA = 0.4` | Tunable constants exposed as class attributes. |
