# 03 — Architectural Invariants

Seven invariants are enforced *in code*, not in docs. If any of them gets violated, the failure is loud — either an `AssertionError`, a typed exception, or a test failure. None are settings to be tuned per-deployment.

---

## 1. T-1 lag on factor regressions

**Where:** [src/advisory/layer4_risk/fundamental.py](../src/advisory/layer4_risk/fundamental.py) — `FundamentalRiskModel._aligned_lagged_inputs`

**What:** factor returns at date T must come from `factor_returns.shift(1)` (i.e., the *prior* trading day's factor returns). The method:

1. Computes `lagged_factors = factor_returns.shift(1)`.
2. Joins lagged factors with the asset return at T.
3. **Asserts** that the lagged values equal the shifted-by-one values of the original input — directly.

```python
assert np.allclose(
    lagged_factors[ref_col].to_numpy(),
    original_prev.to_numpy(),
    equal_nan=True,
), (
    "T-1 lag assertion failed: lagged factor values do not match "
    "the shift(1) of the input factor returns. This is a "
    "look-ahead contamination. Halting."
)
```

**Test:** [test_fundamental.py::test_t_minus_1_lag_assertion_fires_when_factors_not_shifted](../tests/unit/test_layer4/test_fundamental.py) monkeypatches `pd.DataFrame.shift` to identity and verifies the `AssertionError` fires.

---

## 2. Winsorisation parity between normaliser and HMM

**Where:** [src/advisory/layer1_market_state/normalizer.py](../src/advisory/layer1_market_state/normalizer.py) + [engine.py](../src/advisory/layer1_market_state/engine.py)

**What:** the EWMA-normaliser and the HMM both clip at `EWMA_CLIP = settings.ewma_clip` (default 4.0). If they differ, the HMM sees a different distribution from the one it was trained on. The constant is read from `config/settings.py` in one place; `ewma_normalize` and `winsorize` both reference it.

The `MarketStateEngine` additionally caches the training mean/std (`attach_training_moments`) and re-applies them at inference time so a regime that drifts the mean does not change the Winsorisation behaviour.

**Test:** [test_normalizer.py::test_output_within_clip_bounds](../tests/unit/test_layer1/test_normalizer.py) inserts a 50σ outlier and verifies clipping; [test_engine.py::test_winsorize_clips_extreme_values](../tests/unit/test_layer1/test_engine.py) verifies the HMM helper.

---

## 3. Interventional SHAP only

**Where:** [src/advisory/layer3_attribution/shap_layer.py](../src/advisory/layer3_attribution/shap_layer.py)

**What:** the constructor calls `shap.TreeExplainer(..., feature_perturbation="interventional")`. If SHAP raises (e.g., because the background dataset shape is wrong), the constructor raises `ConfigurationError` rather than silently fall back to the path-dependent algorithm. Path-dependent SHAP is rejected by the architecture for this domain.

Additionally:
- The model must support `predict_proba` (raises `TypeError` if not).
- Every `explain_asset` call returns a `background_vintage` ISO date string. The dashboard must surface this; it is not optional.
- The background refreshes every 5 calendar days from a 252-day lookback.

**Test:** [test_shap_layer.py::test_non_predict_proba_model_raises](../tests/unit/test_layer3/test_shap_layer.py) and `test_explain_asset_returns_background_vintage`.

---

## 4. FDR correction uses Benjamini-Yekutieli

**Where:** [src/advisory/layer7_hygiene/fdr.py](../src/advisory/layer7_hygiene/fdr.py)

**What:** `apply_fdr_correction` calls `multipletests(..., method="fdr_by")`. BH (Benjamini-Hochberg) is rejected because it controls FDR only under independence or positive regression dependency. Financial features have complex, time-varying, sometimes strongly negative cross-correlations — BY's arbitrary-dependence guarantee is required. BY is more conservative; this is correct.

The module carries a comment explaining this; the test enforces the kwarg:

```python
with patch("src.advisory.layer7_hygiene.fdr.multipletests", ...) as mock:
    apply_fdr_correction(alerts)
_, kwargs = mock.call_args
assert kwargs.get("method") == "fdr_by"
```

**Test:** [test_fdr.py::test_by_method_is_used](../tests/unit/test_layer7/test_fdr.py)

---

## 5. Deflated Sharpe trial count cannot be understated

**Where:** [src/advisory/layer0_validation/deflated_sharpe.py](../src/advisory/layer0_validation/deflated_sharpe.py)

**What:** the function signature reads `audit_log: AuditLog` — not `n_trials: int`. It reads `audit_log.trial_count()` internally. `n_trials = max(audit_count, STATIC_TRIAL_FLOOR=2000)`. The caller cannot pass a smaller number.

`AuditLog` is append-only DuckDB. The trial count is the row count of `backtest_executions`, not a separate column, so a half-written insert cannot drift it. Every CPCV / walk-forward run records *before* fitting so a crash mid-run still costs a trial.

**Test:** [test_deflated_sharpe.py::test_n_trials_floored_at_static_floor](../tests/unit/test_layer0/test_deflated_sharpe.py) and `test_dsr_monotone_decreasing_in_trial_count`.

---

## 6. Kelly absolute cap of 20%

**Where:** [src/advisory/layer10_sizing/diagnostics.py](../src/advisory/layer10_sizing/diagnostics.py)

**What:** `KELLY_ABSOLUTE_CAP = 0.20`. Every Kelly variant (`raw_kelly`, `haircut_kelly_standard`, `haircut_kelly_regime`, `displayed_kelly`) is clamped by `_cap`. The displayed cap is part of the output so the trader can see it on the dashboard.

The Kelly loss term is `|ES_5|` (5th-percentile expected shortfall), not the arithmetic mean of negative returns. On small heavy-tailed samples, the mean understates expected loss because rare large losses get averaged with many small losses.

The regime haircut multiplies by `(1 - state_uncertainty) * min(1.0, hmm_analog_overlap_pct * 1.5)`. At full uncertainty + zero overlap this yields 0.0, producing a displayed Kelly of 0.0 — the architecture forbids clamping at a non-zero floor.

**Tests:** [test_diagnostics.py::test_kelly_capped_at_absolute_cap](../tests/unit/test_layer10/test_diagnostics.py), `test_es5_used_as_loss_term_not_mean_loss`, `test_zero_confidence_produces_zero_regime_kelly`, and a property test sweeping 20 random configs.

---

## 7. Paper-trading fills on the adverse side of the spread

**Where:** [src/advisory/paper_trading/harness.py](../src/advisory/paper_trading/harness.py)

**What:** `RealisticExecutionHarness.simulate_fill` returns a fill price that is *strictly* on the adverse side:

- Buy: `fill_price = ask * (1 + impact) + friction`. Then `assert fill_price >= ask`.
- Sell: `fill_price = bid * (1 - impact) - friction`. Then `assert fill_price <= bid`.

Midpoint fills are impossible by construction. Friction (`vol_z` + `spread_z`) only adds to slippage; it never subtracts. Impact is square-root in `order_size / ADV`.

**Tests:** [test_harness.py::test_buy_fill_at_or_above_ask](../tests/unit/test_paper_trading/test_harness.py), `test_sell_fill_at_or_below_bid`, and a property test sweeping vol scenarios.

---

## What about CPCV embargo, MIN_N_OBS, CRISIS_WINDOWS, etc.?

Those are pinned constants but they are not invariants — they can be changed via a known process. Changing them invalidates the validation reports calibrated against them and triggers re-validation; they are *not* runtime-tunable. Constants live next to their consumer with a comment when the rationale is non-obvious (e.g., the 504-day CPCV embargo floor is anchored to the longest model lookback, tail betas).
