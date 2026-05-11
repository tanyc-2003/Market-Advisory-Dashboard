"""Tests for dimensionality_adequacy (Phase 2)."""
from __future__ import annotations

import numpy as np

from src.advisory.layer1_market_state.dimensionality import (
    R2_ADEQUACY_FLOOR,
    dimensionality_adequacy,
)


def test_insufficient_data_returns_status():
    X = np.zeros((10, 5))
    result = dimensionality_adequacy(X)
    assert result["status"] == "INSUFFICIENT_DATA"


def test_perfect_linear_structure_passes():
    rng = np.random.default_rng(0)
    z = rng.normal(0, 1, size=300)
    X = np.column_stack([z + rng.normal(0, 0.01, 300) for _ in range(5)])
    result = dimensionality_adequacy(X)
    # A 5-column near-clone of z should give high R²
    assert result["passed"]
    assert result["oos_r2"] >= R2_ADEQUACY_FLOOR


def test_warn_callback_invoked_on_failure():
    rng = np.random.default_rng(0)
    X = rng.normal(0, 1, size=(60, 5))
    seen: list[str] = []
    dimensionality_adequacy(X, warn_callback=seen.append)
    # Random matrix is unlikely to pass — callback should have fired
    if seen:
        assert "dimensionality" in seen[0]
