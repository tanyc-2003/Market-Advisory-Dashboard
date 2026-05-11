"""Tests for SignalAttributionLayer (Phase 4)."""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pytest
from sklearn.ensemble import RandomForestClassifier

from src.advisory.layer3_attribution.shap_layer import (
    REDUNDANCY_DOMINANCE_THRESHOLD,
    SignalAttributionLayer,
    detect_factor_redundancy,
)


def _train_model(rng) -> tuple[RandomForestClassifier, np.ndarray, list[str]]:
    n = 600
    X = rng.normal(0, 1, size=(n, 5))
    # Make feature 0 the dominant driver.
    y = (X[:, 0] + 0.3 * rng.normal(0, 1, n) > 0).astype(int)
    model = RandomForestClassifier(n_estimators=40, random_state=0).fit(X, y)
    return model, X, [f"f{i}" for i in range(5)]


def test_explain_asset_returns_background_vintage():
    rng = np.random.default_rng(0)
    model, X, cols = _train_model(rng)
    today = date(2024, 6, 1)

    def background_provider(_d):
        return X[:200]

    layer = SignalAttributionLayer(
        model=model,
        feature_cols=cols,
        background_provider=background_provider,
        today=today,
    )
    result = layer.explain_asset(X[-1], ticker="TST", as_of=today)
    assert result["background_vintage"] == today.isoformat()
    assert result["ticker"] == "TST"


def test_explain_asset_returns_all_contributions():
    rng = np.random.default_rng(0)
    model, X, cols = _train_model(rng)
    today = date(2024, 6, 1)
    layer = SignalAttributionLayer(
        model=model,
        feature_cols=cols,
        background_provider=lambda _d: X[:200],
        today=today,
    )
    result = layer.explain_asset(X[-1], ticker="TST", as_of=today)
    assert len(result["all_contributions"]) == len(cols)


def test_non_predict_proba_model_raises():
    class Bare:
        pass

    with pytest.raises(TypeError):
        SignalAttributionLayer(
            model=Bare(),
            feature_cols=["a"],
            background_provider=lambda _d: np.zeros((10, 1)),
            today=date(2024, 1, 1),
        )


def test_background_refreshes_after_staleness():
    rng = np.random.default_rng(0)
    model, X, cols = _train_model(rng)
    today = date(2024, 6, 1)
    calls: list[date] = []

    def background_provider(d):
        calls.append(d)
        return X[:200]

    layer = SignalAttributionLayer(
        model=model,
        feature_cols=cols,
        background_provider=background_provider,
        today=today,
    )
    n_initial = len(calls)
    layer.explain_asset(X[-1], "TST", as_of=today + timedelta(days=10))
    assert len(calls) > n_initial


def test_detect_redundancy_warns_when_dominated():
    attributions = [
        {"top_features": ["earnings_revision_z", "x", "y"]} for _ in range(6)
    ] + [
        {"top_features": ["other", "x", "y"]} for _ in range(2)
    ]
    result = detect_factor_redundancy(attributions)
    assert result["redundancy_warning"]
    assert result["dominant_driver"] == "earnings_revision_z"
    assert result["dominance_share"] >= REDUNDANCY_DOMINANCE_THRESHOLD


def test_detect_redundancy_no_warning_when_diverse():
    attributions = [
        {"top_features": [f"feature_{i}", "x", "y"]} for i in range(8)
    ]
    result = detect_factor_redundancy(attributions)
    assert not result["redundancy_warning"]
