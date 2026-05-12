"""Tests for the two-regime covariance and stress test (Phase 6)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.advisory.layer6_portfolio.covariance import (
    STRESS_NOTE,
    STRESS_SCENARIOS,
    fit_two_regime_covariance,
    list_scenarios,
    run_stress_test,
)


def _returns(n: int = 1500, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2007-01-01", periods=n)
    return pd.DataFrame(
        rng.normal(0, 0.01, size=(n, 5)),
        index=idx,
        columns=[f"T{i}" for i in range(5)],
    )


def test_normal_and_stressed_cov_are_psd():
    out = fit_two_regime_covariance(_returns())
    for key in ("normal_cov", "stressed_cov"):
        eigs = np.linalg.eigvalsh(out[key])
        assert (eigs > -1e-8).all(), f"{key} not PSD: min eig = {eigs.min()}"


def test_stress_test_returns_all_fields():
    out = fit_two_regime_covariance(_returns())
    weights = np.array([0.2, 0.2, 0.2, 0.2, 0.2])
    betas = {"market_beta": 1.0, "credit_sensitivity": 0.4}
    result = run_stress_test(
        "2008_credit_crunch",
        weights,
        betas,
        out,
    )
    assert "factor_impact" in result
    assert "stressed_vol" in result
    assert result["note"] == STRESS_NOTE


def test_list_scenarios_returns_all_defined():
    assert set(list_scenarios()) == set(STRESS_SCENARIOS.keys())


def test_unknown_scenario_raises():
    out = fit_two_regime_covariance(_returns())
    import pytest

    with pytest.raises(KeyError):
        run_stress_test(
            "nope",
            np.array([0.5, 0.5, 0, 0, 0]),
            {},
            out,
        )
