"""Pre-trade impact preview.

Shows the diff between portfolio vol/factor exposures *before* and *after*
the candidate position is added at ``target_weight``.  Weights are
exactly normalised; the assertion below is the architectural guarantee.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class PositionImpactResult:
    ticker: str
    vol_before: float
    vol_after: float
    vol_change: float
    factor_additions: dict[str, float]
    effective_n_change: float
    eff_n_before: float = 0.0
    eff_n_after: float = 0.0
    error: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)


T_STAT_SIGNIFICANCE: float = 1.96


def _eff_n(weights: np.ndarray) -> float:
    s = float(np.sum(weights**2))
    return 1.0 / s if s > 0 else 0.0


def _portfolio_vol(weights: np.ndarray, cov: np.ndarray) -> float:
    return float(np.sqrt(max(weights @ cov @ weights, 0.0)))


def preview_position_impact(
    ticker: str,
    target_weight: float,
    universe_tickers: list[str],
    current_weights: dict[str, float],
    covariance_matrix: np.ndarray,
    asset_exposures: dict[str, dict[str, dict[str, Any]]],
) -> PositionImpactResult:
    """Diff portfolio diagnostics before vs after adding ``ticker``.

    Parameters
    ----------
    asset_exposures:
        Mapping ``ticker -> {factor: {beta, t_stat, significant}}`` as
        produced by :func:`FundamentalRiskModel.fit_ew_ols`.
    """
    if ticker not in universe_tickers:
        return PositionImpactResult(
            ticker=ticker,
            vol_before=0.0,
            vol_after=0.0,
            vol_change=0.0,
            factor_additions={},
            effective_n_change=0.0,
            error=f"{ticker} not in universe",
        )

    n = len(universe_tickers)
    idx = {t: i for i, t in enumerate(universe_tickers)}

    w_current = np.array(
        [current_weights.get(t, 0.0) for t in universe_tickers], dtype=float
    )
    target_idx = idx[ticker]

    eff_n_before = _eff_n(w_current)
    if w_current.sum() < 1e-12:
        vol_before = 0.0
        w_new = np.zeros(n, dtype=float)
        w_new[target_idx] = target_weight
        # Renormalise the rest to fill (1 - target_weight); but with empty
        # portfolio there's nothing to fill, so just leave the candidate.
    else:
        vol_before = _portfolio_vol(w_current, covariance_matrix)
        # Scale the current portfolio to fill (1 - target_weight); zero
        # the candidate first.
        w_current_renorm = w_current.copy()
        w_current_renorm[target_idx] = 0.0
        s = w_current_renorm.sum()
        if s > 0:
            w_current_renorm = w_current_renorm * (1.0 - target_weight) / s
        w_new = w_current_renorm
        w_new[target_idx] = target_weight

    assert abs(w_new.sum() - (target_weight if w_current.sum() < 1e-12 else 1.0)) < 1e-9, (
        "Weights do not sum to expected total after rescaling."
    )

    vol_after = _portfolio_vol(w_new, covariance_matrix)
    eff_n_after = _eff_n(w_new)

    # Factor additions: candidate's significant betas weighted by
    # ``target_weight``.
    factor_additions: dict[str, float] = {}
    for f, info in asset_exposures.get(ticker, {}).items():
        if info.get("significant", False):
            factor_additions[f] = float(info["beta"]) * target_weight

    return PositionImpactResult(
        ticker=ticker,
        vol_before=vol_before,
        vol_after=vol_after,
        vol_change=vol_after - vol_before,
        factor_additions=factor_additions,
        effective_n_change=eff_n_after - eff_n_before,
        eff_n_before=eff_n_before,
        eff_n_after=eff_n_after,
    )
