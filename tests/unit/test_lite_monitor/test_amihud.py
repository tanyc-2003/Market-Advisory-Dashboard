"""V7_lite Phase 6: Amihud illiquidity properties."""
from __future__ import annotations

import numpy as np
import pytest

from src.advisory.layer5_stress.lite_monitor import (
    AMIHUD_DOLLAR_VOLUME_FLOOR,
    amihud_illiquidity,
)


def test_strictly_non_negative():
    rng = np.random.default_rng(0)
    close = 100 * np.cumprod(1 + rng.normal(0, 0.01, size=200))
    volume = rng.uniform(1e6, 5e6, size=200)
    out = amihud_illiquidity(close, volume)
    assert (out >= 0).all()


def test_length_is_n_minus_1():
    close = np.linspace(100, 110, 50)
    volume = np.full(50, 1e6)
    out = amihud_illiquidity(close, volume)
    assert out.size == 49


def test_spikes_on_large_return_with_low_volume():
    close = np.array([100.0, 100.0, 100.0, 60.0])  # 40% drop
    volume = np.array([1e6, 1e6, 1e6, 1e4])
    out = amihud_illiquidity(close, volume)
    # Last observation has both large |log return| and small dollar volume
    assert out[-1] > out[0]


def test_floor_prevents_division_by_zero():
    close = np.array([100.0, 110.0])
    volume = np.array([1e6, 0.0])
    out = amihud_illiquidity(close, volume)
    assert np.isfinite(out).all()
    # Manually verify: |log(110/100)| / max(110*0, FLOOR) == log(1.1) / FLOOR
    expected = abs(np.log(110.0 / 100.0)) / AMIHUD_DOLLAR_VOLUME_FLOOR
    assert out[0] == pytest.approx(expected, rel=1e-9)
