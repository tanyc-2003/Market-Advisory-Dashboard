# 01 — System Overview

## Purpose

The Market Advisory Dashboard is a single-trader market-intelligence system. It does not place trades, generate signals, or recommend position sizes. Its only job is to **surface what is and is not statistically supported about a market state**, with explicit error bars around every claim, and to refuse to display anything that has not passed the Layer 0 validation gate.

The system targets the failure mode where a trader builds a sophisticated dashboard, sees confident-sounding outputs, and treats them as evidence even when the underlying models are not validated. We invert that: confidence language is gated on statistics, not on UI polish.

## Core invariant

> No layer output is treated as evidence until its `ValidationReport.production_ready == True`.

Every other layer — historical analogs, regime detection, attribution, factor risk, portfolio diagnostics, position sizing — is wrapped in this gate. `ValidationReport.status` returns one of three strings, and the dashboard renders accordingly:

| Status | What it means | UI behaviour |
|---|---|---|
| `production` | All five sign-off criteria pass | render normally |
| `research_preview` | One or more criteria fail but not survivorship and not negative WF Sharpe | render with a banner |
| `blocked` | Survivorship audit failed OR walk-forward Sharpe negative | hide the output |

The decorator `requires_production` enforces this in code:

```python
@requires_production(lambda: my_report)
def expensive_layer_method(): ...
```

If `my_report.production_ready` is `False`, the call raises `ValidationGateError` before doing any work. The dashboard catches the error and falls back to the banner / hide behaviour above.

## The five sign-off criteria

`validate_layer(report)` in [src/advisory/layer0_validation/report.py](../src/advisory/layer0_validation/report.py) checks five things:

1. **Survivorship audit passed** — the live universe contains a plausible representation of delisted tickers (coverage >= 0.95 by default; floor 0.80).
2. **Walk-forward Sharpe >= floor** — default floor 0.5.
3. **Walk-forward ECE <= ceiling** — Expected Calibration Error must be <= 0.05.
4. **CPCV 30th-percentile Sharpe >= floor** — default floor 0.0; the harsh-path bar must be non-negative.
5. **Deflated Sharpe >= floor** — default 0.95; computed as `Φ(z)` where `z` accounts for the number of trials in the audit log AND the floor of 2000.

If all five pass, `production_ready = True` and the layer's output is treated as evidence. If any fail, the report carries a human-readable `rationale` string that the dashboard surfaces alongside the banner.

## Why this matters

The "research preview" tier is the one that earns its keep. A model can produce a positive backtest Sharpe and still fail Deflated Sharpe (because we tried a lot of things) or still fail calibration (because we are uniformly overconfident). The Deflated Sharpe pulls the floor of `n_trials` from a monotonic DuckDB audit log so we cannot pretend we ran fewer trials than we did. The calibration system uses reliability diagrams, not Spearman, because uniformly overconfident traders pass Spearman trivially.

These are not optimisations on top of the trading pipeline — they are the pipeline. Everything else exists to feed them.
