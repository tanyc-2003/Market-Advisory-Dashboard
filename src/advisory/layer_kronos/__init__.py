"""Kronos probabilistic OHLCV forecaster (Tier 3 #9).

A self-contained, validated-only forecasting model that produces probabilistic
forward-return bands with the Kronos deliverable shape (median path + p5–p95 fan,
P(up), P(vol regime shift)). The concrete backend here is a regime-aware
block-bootstrap Monte-Carlo forecaster — real, runnable on our data with existing
deps, and put through the same Layer 0 gate (walk-forward → deflated Sharpe →
promote) as the HMM.

The pretrained Kronos transformer (torch + HF weights, Apache-2.0) can replace
the model backend behind the same `KronosForecaster.forecast(...)` interface
without touching the API wiring, the gate, or the scripts.
"""
