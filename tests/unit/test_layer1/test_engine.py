"""Tests for the Winsorised HMM engine (Phase 2)."""
from __future__ import annotations

import numpy as np

from src.advisory.layer1_market_state.engine import (
    TRANSITION_UNCERTAINTY_THRESHOLD,
    train_market_state_engine,
    winsorize,
)
from src.advisory.layer0_validation.audit_log import AuditLog


def test_winsorize_clips_extreme_values():
    rng = np.random.default_rng(0)
    x = rng.normal(0, 1, size=(200, 3))
    x[0, 0] = 50.0
    w = winsorize(x, sigma_cap=4.0)
    # Check the outlier got pulled in
    assert w[0, 0] < x[0, 0]
    sd = np.nanstd(x, axis=0, ddof=1)
    mu = np.nanmean(x, axis=0)
    z = (w - mu) / sd
    assert (np.abs(z) <= 4.0 + 1e-6).all()


def test_winsorize_does_not_modify_inliers():
    rng = np.random.default_rng(0)
    x = rng.normal(0, 1, size=(200, 3))
    w = winsorize(x, sigma_cap=4.0)
    # On clean Gaussian data, nothing should hit the cap
    np.testing.assert_allclose(w, x, atol=1e-9)


def test_state_engine_emits_valid_probability_vector(
    synthetic_feature_history, feature_cols
):
    log = AuditLog(":memory:")
    try:
        engine = train_market_state_engine(
            synthetic_feature_history.head(400),
            feature_cols,
            k=3,
            audit_log=log,
        )
        obs = engine.get_current_state(synthetic_feature_history.tail(50))
    finally:
        log.close()
    assert abs(obs.state_probs.sum() - 1.0) < 1e-6
    assert 0 <= obs.dominant_state_id < 3
    assert 0.0 <= obs.state_uncertainty <= 1.0


def test_decode_path_returns_state_ids(synthetic_feature_history, feature_cols):
    log = AuditLog(":memory:")
    try:
        engine = train_market_state_engine(
            synthetic_feature_history.head(400),
            feature_cols,
            k=3,
            audit_log=log,
        )
        path = engine.decode_path(synthetic_feature_history.head(400))
    finally:
        log.close()
    assert path.shape == (400,)
    assert set(np.unique(path).tolist()).issubset({0, 1, 2})


def test_transition_threshold_constant():
    assert 0 < TRANSITION_UNCERTAINTY_THRESHOLD < 1
