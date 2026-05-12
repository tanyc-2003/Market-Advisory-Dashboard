"""Tests for ResidualFactorAnomalyDetector (Phase 5)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.advisory.layer4_risk.residual_pca import (
    ResidualFactorAnomalyDetector,
)


def _residuals_with_hidden_cluster(seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n_obs = 300
    # 5 tickers; tickers 0-3 share a hidden common factor.
    z = rng.normal(0, 1, size=n_obs)
    data = {
        "A": z + rng.normal(0, 0.2, n_obs),
        "B": z + rng.normal(0, 0.2, n_obs),
        "C": z + rng.normal(0, 0.2, n_obs),
        "D": z + rng.normal(0, 0.2, n_obs),
        "E": rng.normal(0, 1.0, n_obs),
    }
    return pd.DataFrame(data, index=pd.bdate_range("2020-01-01", periods=n_obs))


def test_bootstrap_uses_fixed_seed():
    res = _residuals_with_hidden_cluster()
    det = ResidualFactorAnomalyDetector(bootstrap_n=30, seed=42)
    a = det.detect_hidden_concentration(res)
    b = det.detect_hidden_concentration(res)
    assert a == b  # deterministic


def test_alerts_are_human_readable_strings():
    res = _residuals_with_hidden_cluster()
    det = ResidualFactorAnomalyDetector(bootstrap_n=30, seed=42)
    out = det.detect_hidden_concentration(res)
    for alert in out["alerts"]:
        assert isinstance(alert["message"], str)
        assert "Hidden residual factor" in alert["message"]


def test_min_3_tickers_for_cluster():
    res = _residuals_with_hidden_cluster()
    det = ResidualFactorAnomalyDetector(bootstrap_n=30, seed=42)
    out = det.detect_hidden_concentration(res)
    for alert in out["alerts"]:
        assert alert["n_members"] >= 3
