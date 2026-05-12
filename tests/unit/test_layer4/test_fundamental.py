"""Tests for FundamentalRiskModel (Phase 5)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.advisory.layer0_validation.audit_log import AuditLog
from src.advisory.layer4_risk.factors import FACTOR_ORDER
from src.advisory.layer4_risk.fundamental import (
    MIN_N_OBS,
    AssetExposureResult,
    FundamentalRiskModel,
)


def _synthetic_factors(n: int = 600, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2020-01-01", periods=n)
    data = rng.normal(0, 0.01, size=(n, len(FACTOR_ORDER)))
    return pd.DataFrame(data, index=idx, columns=FACTOR_ORDER)


def _synthetic_asset(factors: pd.DataFrame, seed: int = 1) -> pd.Series:
    rng = np.random.default_rng(seed)
    true_betas = np.array([0.9, -0.2, 0.3, 0.4, 0.1, 0.0, 0.05, 0.1, 0.2, 0.15])
    # Asset return at T responds to factor returns at T-1.
    lagged = factors.shift(1).fillna(0.0).to_numpy()
    noise = rng.normal(0, 0.005, size=len(factors))
    y = lagged @ true_betas + noise
    return pd.Series(y, index=factors.index, name="X")


def test_ew_ols_returns_all_factor_keys():
    log = AuditLog(":memory:")
    model = FundamentalRiskModel(log)
    factors = _synthetic_factors()
    asset = _synthetic_asset(factors)
    result = model.fit_ew_ols("X", factors, asset)
    assert result["status"] == "OK"
    assert result["lag_enforced"] is True
    for f in FACTOR_ORDER:
        assert f in result["factor_exposures"]


def test_insufficient_data_returns_skipped():
    log = AuditLog(":memory:")
    model = FundamentalRiskModel(log)
    factors = _synthetic_factors(n=MIN_N_OBS - 1)
    asset = _synthetic_asset(factors)
    result = model.fit_ew_ols("X", factors, asset)
    assert result["status"] == "SKIPPED_INSUFFICIENT_DATA"


def test_ridge_lag_enforced():
    log = AuditLog(":memory:")
    model = FundamentalRiskModel(log)
    factors = _synthetic_factors()
    asset = _synthetic_asset(factors)
    result = model.fit_ridge("X", factors, asset)
    assert result["lag_enforced"] is True


def test_tail_betas_returns_downside_and_upside():
    log = AuditLog(":memory:")
    model = FundamentalRiskModel(log)
    factors = _synthetic_factors()
    asset = _synthetic_asset(factors)
    result = model.fit_tail_betas("X", factors, asset)
    assert result["status"] == "OK"
    assert set(result["tail_betas"].keys()) == {"downside_5", "upside_95"}


def test_t_minus_1_lag_assertion_fires_when_factors_not_shifted():
    log = AuditLog(":memory:")
    model = FundamentalRiskModel(log)
    factors = _synthetic_factors()
    asset = _synthetic_asset(factors)
    # Monkey-patch shift to be identity to simulate an accidental
    # removal of the lag.
    import pandas as pd

    original_shift = pd.DataFrame.shift

    def no_shift(self, *_args, **_kwargs):
        return self

    pd.DataFrame.shift = no_shift  # type: ignore[assignment]
    try:
        with pytest.raises(AssertionError):
            model.fit_ew_ols("X", factors, asset)
    finally:
        pd.DataFrame.shift = original_shift  # type: ignore[assignment]


def test_to_dataclass_wraps_result():
    log = AuditLog(":memory:")
    model = FundamentalRiskModel(log)
    factors = _synthetic_factors()
    asset = _synthetic_asset(factors)
    result = model.fit_ew_ols("X", factors, asset)
    wrapped = model.to_dataclass(result)
    assert isinstance(wrapped, AssetExposureResult)
    assert wrapped.lag_enforced is True
