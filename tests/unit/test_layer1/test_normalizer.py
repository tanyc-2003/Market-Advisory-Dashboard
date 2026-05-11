"""Tests for the EWMA normalizer (Phase 2)."""
from __future__ import annotations

import numpy as np

from src.advisory.layer1_market_state.normalizer import EWMA_CLIP, ewma_normalize


def test_output_within_clip_bounds():
    rng = np.random.default_rng(0)
    x = rng.normal(0, 1, size=500)
    x[100] = 50.0  # extreme outlier
    z = ewma_normalize(x, half_life=42)
    assert (z >= -EWMA_CLIP).all() and (z <= EWMA_CLIP).all()


def test_constant_series_returns_zero():
    x = np.ones(100)
    z = ewma_normalize(x, half_life=10)
    assert np.allclose(z, 0.0)


def test_empty_input_returns_empty():
    z = ewma_normalize(np.array([]), half_life=10)
    assert z.size == 0
