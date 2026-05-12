"""V7_lite Phase 10: Layer 3 + Layer 4 lock guards."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import RandomForestClassifier

from src.advisory.layer0_validation.audit_log import AuditLog
from src.advisory.layer3_attribution.shap_layer import (
    LAYER3_LOCK_MESSAGE,
    SignalAttributionLayer,
)
from src.advisory.layer4_risk.factors import FACTOR_ORDER
from src.advisory.layer4_risk.fundamental import (
    LAYER4_LOCK_MESSAGE,
    FundamentalRiskModel,
)


def test_layer3_returns_locked_in_v7_lite():
    rng = np.random.default_rng(0)
    layer = SignalAttributionLayer(
        model=object(),  # would normally fail predict_proba; ignored in lite
        feature_cols=["a", "b", "c"],
        background_provider=lambda d: np.zeros((50, 3)),
        today=date(2024, 1, 1),
        app_mode="v7_lite",
    )
    out = layer.explain_asset(np.zeros(3), ticker="AAPL", as_of=date(2024, 1, 1))
    assert out["status"] == "LOCKED"
    assert out["message"] == LAYER3_LOCK_MESSAGE


def test_layer3_functional_in_institutional_mode():
    rng = np.random.default_rng(0)
    X = rng.normal(0, 1, size=(600, 3))
    y = (X[:, 0] > 0).astype(int)
    model = RandomForestClassifier(n_estimators=20, random_state=0).fit(X, y)
    layer = SignalAttributionLayer(
        model=model,
        feature_cols=["a", "b", "c"],
        background_provider=lambda d: X[:200],
        today=date(2024, 1, 1),
        app_mode="v7_institutional",
    )
    out = layer.explain_asset(X[-1], ticker="AAPL", as_of=date(2024, 1, 1))
    assert out.get("status") != "LOCKED"
    assert "all_contributions" in out


def test_layer4_returns_locked_in_v7_lite():
    log = AuditLog(":memory:")
    model = FundamentalRiskModel(log, app_mode="v7_lite")
    out = model.fit_ew_ols(
        "AAPL",
        pd.DataFrame({f: [0.01] * 100 for f in FACTOR_ORDER}),
        pd.Series([0.005] * 100),
    )
    assert out["status"] == "LOCKED"
    assert out["message"] == LAYER4_LOCK_MESSAGE


def test_layer4_all_three_methods_locked():
    log = AuditLog(":memory:")
    model = FundamentalRiskModel(log, app_mode="v7_lite")
    factors = pd.DataFrame({f: [0.01] * 100 for f in FACTOR_ORDER})
    asset = pd.Series([0.005] * 100)
    assert model.fit_ew_ols("X", factors, asset)["status"] == "LOCKED"
    assert model.fit_ridge("X", factors, asset)["status"] == "LOCKED"
    assert model.fit_tail_betas("X", factors, asset)["status"] == "LOCKED"


def test_layer4_institutional_unchanged():
    log = AuditLog(":memory:")
    model = FundamentalRiskModel(log, app_mode="v7_institutional")
    # We don't need a fully realistic dataset — just verify no LOCKED short-circuit.
    factors = pd.DataFrame(
        {f: np.random.default_rng(0).normal(0, 0.01, 600) for f in FACTOR_ORDER},
        index=pd.bdate_range("2020-01-01", periods=600),
    )
    asset = pd.Series(np.random.default_rng(1).normal(0, 0.01, 600), index=factors.index)
    out = model.fit_ew_ols("X", factors, asset)
    assert out["status"] != "LOCKED"
