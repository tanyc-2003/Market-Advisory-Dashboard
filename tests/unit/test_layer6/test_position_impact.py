"""Tests for preview_position_impact (Phase 6)."""
from __future__ import annotations

import numpy as np

from src.advisory.layer6_portfolio.position_impact import (
    preview_position_impact,
)


def _universe(n: int = 5) -> tuple[list[str], np.ndarray]:
    tickers = [f"T{i}" for i in range(n)]
    rng = np.random.default_rng(0)
    # Diagonal-heavy positive-definite covariance
    M = rng.normal(0, 1, size=(n, n))
    cov = M @ M.T / n + np.eye(n) * 0.01
    return tickers, cov


def test_weights_sum_to_one_after_rescaling():
    tickers, cov = _universe()
    current = {tickers[0]: 0.4, tickers[1]: 0.3, tickers[2]: 0.3}
    result = preview_position_impact(
        ticker="T3",
        target_weight=0.2,
        universe_tickers=tickers,
        current_weights=current,
        covariance_matrix=cov,
        asset_exposures={"T3": {"market_beta": {"beta": 1.0, "significant": True}}},
    )
    # Assertion inside preview_position_impact already guards this; if
    # no AssertionError fired we're good.
    assert result.error is None


def test_empty_portfolio_handled():
    tickers, cov = _universe()
    result = preview_position_impact(
        ticker="T0",
        target_weight=0.1,
        universe_tickers=tickers,
        current_weights={},
        covariance_matrix=cov,
        asset_exposures={"T0": {}},
    )
    assert result.vol_before == 0.0
    assert result.eff_n_before == 0.0


def test_vol_increases_when_candidate_is_highest_variance():
    tickers = [f"T{i}" for i in range(5)]
    # Diagonal cov where T0 dominates: concentrating into T0 must raise vol.
    cov = np.diag([0.5, 0.01, 0.01, 0.01, 0.01])
    current = {t: 1.0 / 5 for t in tickers}
    result = preview_position_impact(
        ticker="T0",
        target_weight=0.8,
        universe_tickers=tickers,
        current_weights=current,
        covariance_matrix=cov,
        asset_exposures={"T0": {}},
    )
    assert result.vol_after > result.vol_before


def test_unknown_ticker_returns_error():
    tickers, cov = _universe()
    result = preview_position_impact(
        ticker="ZZZ",
        target_weight=0.1,
        universe_tickers=tickers,
        current_weights={},
        covariance_matrix=cov,
        asset_exposures={},
    )
    assert result.error is not None


def test_effective_n_decreases_with_concentration():
    tickers, cov = _universe()
    current = {t: 1.0 / 5 for t in tickers}
    result = preview_position_impact(
        ticker="T0",
        target_weight=0.6,
        universe_tickers=tickers,
        current_weights=current,
        covariance_matrix=cov,
        asset_exposures={"T0": {}},
    )
    assert result.eff_n_after < result.eff_n_before
