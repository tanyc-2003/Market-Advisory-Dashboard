# 09 — V7_lite (Scanner+) extension

V7 Institutional assumes Polygon + Sharadar subscriptions for point-in-time fundamentals, delisted-ticker history, and intraday microstructure. Those are several thousand dollars a year. **V7_lite** is a free-data tier built on yfinance, FRED, and CBOE public endpoints.

The tradeoff is real: free data is survivorship-biased (no delisted history), fundamental-poor (no PIT earnings revisions, no analyst surprise), and microstructure-thin (no real intraday spread data). V7_lite is acceptable **only** because every degraded output is wrapped in a permanent, non-dismissible disclosure of the bias. Pretending the system is producing institutional-grade evidence on free data is exactly the failure mode this whole architecture is designed against.

## The three modes

| Mode | Data | Layers active | UI surface |
|---|---|---|---|
| `APP_MODE=v7_lite` (default) | yfinance · FRED · CBOE | All except 3 + 4 | Survivorship-bias panel on every analog-distribution page; locked tiles for Layers 3 + 4 |
| `APP_MODE=v7_institutional` with paid keys | Polygon · Sharadar · FRED · CBOE | All | Full layer set; no bias panels |
| `APP_MODE=v7_institutional` without paid keys | Synthetic | All | Red **Developer Mode** banner |

Mode is read from `.env`. A restart of Streamlit picks up the new value. See [05_running.md](05_running.md) for switch commands.

## What's locked in lite

| Layer | Reason |
|---|---|
| **Layer 3 — Signal Attribution (SHAP)** | Requires a calibrated classifier trained on labelled outcomes. Without survivorship-clean returns + PIT fundamentals, attribution would be misleading. The `SignalAttributionLayer` constructor still works; every output method returns `{"status": "LOCKED"}`. |
| **Layer 4 — Hybrid Risk Model** | Tail-beta regression needs ≥ 504 days of survivorship-clean factor returns. Lite data can't supply that cleanly, so `FundamentalRiskModel.fit_ew_ols` / `fit_ridge` / `fit_tail_betas` return `{"status": "LOCKED"}`. |

Both classes still **instantiate cleanly** in lite mode — they don't crash on import or construction. Only their output methods short-circuit. The dashboard renders a yellow lock tile where these layers would normally surface results.

## Eight V7_lite invariants

In addition to the seven V7 invariants in [03_invariants.md](03_invariants.md):

### 1. Additive only

No V7 Institutional code path is deleted. Every lite-mode behaviour is reached through an `APP_MODE`-gated branch and seven new modules:

- `src/advisory/data_infra/yfinance_adapter.py`
- `src/advisory/data_infra/fred_adapter.py` (PIT-safe)
- `src/advisory/data_infra/cboe_adapter.py`
- `src/advisory/data_infra/feature_pipeline_lite.py`
- `src/advisory/layer1_market_state/registry.py`
- `src/advisory/layer5_stress/lite_monitor.py`
- `src/advisory/layer10_sizing/lite_diagnostics.py`

Only the seven controlled modifications listed in `09_V7LITE_MASTER.md §1` were applied to existing files.

### 2. Amihud ≠ Corwin-Schultz

The `LiteFrictionMonitor` produces two distinct quantities:

- `amihud_illiquidity` → feeds Layer 5's `anomaly_score` and `get_vol_z`
- `corwin_schultz_spread` → feeds the harness `simulate_fill` cost model

Substituting one for the other is forbidden. The `RealisticExecutionHarness.simulate_fill` carries an assertion:

```python
if app_mode == "v7_lite" and friction_proxy is not None:
    assert "cs_spread_execution_proxy" in friction_proxy, (
        "V7_lite: simulate_fill requires cs_spread_execution_proxy. "
        "amihud_z is for Layer 5 stress detection, not fill cost."
    )
```

If you ever try to plumb `amihud_z` into the harness, the test suite + the runtime both halt.

### 3. No survivorship win-rate hack

The naive fix to survivorship bias is `win_rate * (1 - SURVIVORSHIP_WIN_RATE_ADJUSTMENT)`. **That constant does not exist in this codebase** — `grep` confirms. The correct fix is to inject *synthetic wipeouts* into the analog return distribution before Kelly sizing.

`inject_synthetic_wipeouts` uses `rng.binomial(n, p)` — a binomial draw, not a deterministic floor. For `n=50` analogs and `p=0.02` annual impairment rate, ~85% of draws return zero injected wipeouts. Hardcoding `int(n * p) = 1` would be wrong: it would always inject one wipeout regardless of the analog set's representativeness. The docstring carries a 26× failure-mode explanation.

### 4. HY/IG OAS lives in Macro, not Layer 5

In `lite_feature_set_9dim.yaml`, HY OAS and IG OAS sit under the `macro` dimension — they are *macro features*, not microstructure stress signals. Layer 5 sees them via the macro feature, not directly. This avoids double-counting credit stress in the friction monitor.

### 5. FRED is PIT-safe by default in lite

`fetch_fred_pit_safe` uses FRED's vintage API with `realtime_start == realtime_end == observation_date`. This protects against silent restatements (e.g., GDP first / second / third estimates). In lite mode, `fetch_fred_series` routes through the PIT-safe path automatically.

### 6. Survivorship disclosure is permanent

`render_survivorship_panel_permanent` has **no dismiss button**. It is rendered at the top of every page that shows analog distributions (Market State, Watchlist, Sizing). The disclosure surfaces the literature-derived bias estimates from `settings.survivorship_bias_estimate()`:

| Metric | Low estimate | High estimate | Source |
|---|---|---|---|
| Sharpe inflation | +0.10 | +0.30 | Elton & Gruber (1996) |
| Annualised return inflation | +1.0% | +3.0% | + subsequent literature |
| Win-rate inflation | +3 pp | +8 pp | |

### 7. Validation paused, not blocked

Lite mode introduces a new `ValidationStatus`: `VALIDATION_PAUSED_DATA_INTEGRITY`. When the missing-bar fraction or cross-ticker staleness exceeds thresholds, the system reports a **pause**, not a demotion. A pause means "we don't know yet"; a demotion means "we know it failed". The distinction matters for the trader's mental model.

The lite divergence threshold for the continuous validator is `0.40`, looser than the institutional `0.30`, because lite data is noisier. Both thresholds are preserved (the constant rename is the one legitimate exception — both names coexist).

### 8. HMM model registry separates artifacts by mode

`models/hmm_v7_lite.pkl` and `models/hmm_v7_institutional.pkl` are distinct artifacts. The `hmm_model_registry` table tracks candidate models with metadata; `promote_candidate` only promotes when WF CV + DSR pass. The dashboard's `train_hmm.py` and `validate_hmm_candidate.py` enforce this — manual artifact swapping bypasses the gate.

## Lite-specific configuration

All knobs flow through `.env` (and `config/settings.py`):

| Var | Default | Meaning |
|---|---|---|
| `APP_MODE` | `v7_lite` | The mode switch. |
| `DIVERGENCE_THRESHOLD_LITE` | `0.40` | Paper-trade vs backtest Sharpe threshold in lite. |
| `MAX_MISSING_BAR_FRACTION` | `0.02` | Pause validation if exceeded. |
| `MAX_STALE_CROSS_TICKER_FRACTION` | `0.20` | Pause validation if exceeded. |
| `ANNUAL_IMPAIRMENT_RATE` | `0.02` | Binomial draw probability for wipeout injection. |
| `SYNTHETIC_WIPEOUT_RETURN` | `-0.60` | Magnitude of an injected wipeout. |

Survivorship bias estimates (`SURVIVORSHIP_*`) are also tunable per-deployment but the architecture-pinned defaults match Elton & Gruber (1996) and should rarely change.

## Developer Mode

If `APP_MODE=v7_institutional` but the paid keys aren't configured, the dashboard surfaces a **red banner**:

> **V7 Institutional — Developer Mode.** Polygon and Sharadar keys are not configured, so the system is reading synthetic data only. Configure paid API keys in `.env` to switch to the live institutional path, or set `APP_MODE=v7_lite` for free real-data sources.

This state is intentional. It lets a developer exercise the full institutional code paths against synthetic data — the layers don't lock, the survivorship panel doesn't render, the sidebar shows institutional badges — without needing subscriptions. The red banner is non-dismissible to prevent forgetting that the data is fake.

## Testing

The 75 V7_lite tests live in 9 directories:

- `test_layer0_lite/` — `ValidationStatus` enum coverage; `_data_integrity_check` thresholds; lite-mode `reassess` returns `VALIDATION_PAUSED_DATA_INTEGRITY`
- `test_yfinance_adapter/` — retry/backoff, sanity checks, gap detection, audit logging (mocked yfinance)
- `test_fred_adapter/` — `fetch_fred_pit_safe` vintage parameters; missing-value handling
- `test_cboe_adapter/` — DuckDB caching round-trip
- `test_lite_monitor/` — Amihud + CS spread computation; **proxy separation** (substitution raises)
- `test_lite_sizing/` — wipeout injection is binomial, not deterministic; ≥85% of draws return zero for `n=50, p=0.02`
- `test_layer2_lite/` — `feature_quality_note` mentions absent Sharadar features
- `test_layer7_lite/` — `UNTESTABLE_LITE` status surfaces Sharadar-dependent pairs instead of silently dropping
- `test_layer_lite/` — feature pipeline, mode indicator, lock guards on Layers 3 + 4, harness assertion

Run them all with:

```bash
pytest tests/ -v
```

Expected result: **280 passed** (205 V7 baseline + 75 V7_lite).
