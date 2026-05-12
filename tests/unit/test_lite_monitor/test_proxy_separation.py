"""V7_lite Phase 6: Amihud / CS separation invariant."""
from __future__ import annotations

import numpy as np
import polars as pl

from src.advisory.layer5_stress.lite_monitor import (
    LiteFrictionMonitor,
    amihud_illiquidity,
    corwin_schultz_spread,
)


def _ohlcv(seed: int = 0) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    n = 60
    close = 100 * np.cumprod(1 + rng.normal(0.0, 0.01, n))
    return pl.DataFrame(
        {
            "ticker": ["SPY"] * n,
            "effective_date": [None] * n,
            "open": close,
            "high": close * 1.005,
            "low": close * 0.995,
            "close": close,
            "volume": np.full(n, 1e6),
        }
    )


def test_compute_friction_proxy_returns_both_fields():
    monitor = LiteFrictionMonitor()
    out = monitor.compute_friction_proxy("SPY", _ohlcv())
    assert "amihud_z" in out
    assert "cs_spread_execution_proxy" in out
    assert out["status"] == "OK"


def test_anomaly_score_equals_amihud_z():
    monitor = LiteFrictionMonitor()
    out = monitor.compute_friction_proxy("SPY", _ohlcv())
    assert out["anomaly_score"] == out["amihud_z"]


def test_get_vol_z_returns_amihud_not_cs():
    monitor = LiteFrictionMonitor()
    out = monitor.compute_friction_proxy("SPY", _ohlcv())
    assert monitor.get_vol_z("SPY") == out["amihud_z"]


def test_cs_floored_at_zero():
    # Construct a series where alpha goes negative — CS should clamp to 0.
    high = np.array([100.0, 100.0, 100.0])
    low = np.array([99.99, 99.99, 99.99])
    out = corwin_schultz_spread(high, low)
    assert (out >= 0).all()


def test_amihud_independent_of_high_low():
    # Verify amihud only consumes close+volume, not high/low.
    close = np.array([100.0, 102.0, 101.0])
    vol = np.array([1e6, 1e6, 1e6])
    out = amihud_illiquidity(close, vol)
    assert out.size == 2
