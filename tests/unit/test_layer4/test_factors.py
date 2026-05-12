"""Tests for the factor orthogonalisation (Phase 5)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.advisory.layer4_risk.factors import FACTOR_ORDER, orthogonalize_factors


def _factor_frame(n: int = 600, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    base = rng.normal(0, 0.01, size=(n, len(FACTOR_ORDER)))
    # Introduce strong cross-correlation so orthogonalisation has work to do.
    base[:, 1] += 0.6 * base[:, 0]
    base[:, 2] += 0.4 * base[:, 0] + 0.3 * base[:, 1]
    idx = pd.bdate_range("2020-01-01", periods=n)
    return pd.DataFrame(base, index=idx, columns=FACTOR_ORDER)


def test_orthogonalisation_produces_uncorrelated_factors():
    raw = _factor_frame()
    orth = orthogonalize_factors(raw)
    corr = np.array(orth.corr().to_numpy(), copy=True)
    np.fill_diagonal(corr, 0.0)
    assert (np.abs(corr) < 0.05).all(), f"max off-diag corr = {np.nanmax(np.abs(corr))}"


def test_factor_order_preserved():
    orth = orthogonalize_factors(_factor_frame())
    assert list(orth.columns) == FACTOR_ORDER


def test_market_beta_first_factor_unchanged():
    raw = _factor_frame()
    orth = orthogonalize_factors(raw)
    np.testing.assert_allclose(
        raw[FACTOR_ORDER[0]].to_numpy(), orth[FACTOR_ORDER[0]].to_numpy()
    )


def test_near_zero_variance_factor_skipped_gracefully():
    raw = _factor_frame()
    raw["volatility_factor"] = 0.0
    orth = orthogonalize_factors(raw)
    # Constant column should remain constant after pass-through.
    assert orth["volatility_factor"].std() == 0
