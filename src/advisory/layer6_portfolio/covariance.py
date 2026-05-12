"""Two-regime covariance and stress scenario engine."""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd
import structlog
from sklearn.covariance import LedoitWolf, MinCovDet

logger = structlog.get_logger(__name__)


# Architecture-pinned crisis windows. Changing the list invalidates every
# stress-test calibration that was performed against the prior windows.
CRISIS_WINDOWS: list[tuple[str, str]] = [
    ("2008-09-15", "2009-03-31"),
    ("2011-08-01", "2011-10-31"),
    ("2020-02-19", "2020-04-30"),
    ("2022-06-13", "2022-10-31"),
]

MCD_MIN_OBS_PER_FEATURE: int = 5

STRESS_NOTE: str = (
    "Stressed-regime covariance was used; normal-regime covariance would "
    "understate this impact."
)


# Named stress scenarios. Each scenario is a {factor_name: shock_in_std} dict.
STRESS_SCENARIOS: dict[str, dict[str, float]] = {
    "2008_credit_crunch": {
        "market_beta": -3.0,
        "credit_sensitivity": -3.5,
        "volatility_factor": -2.5,
    },
    "2020_covid_crash": {
        "market_beta": -4.0,
        "volatility_factor": -4.5,
        "credit_sensitivity": -2.0,
    },
    "2022_rate_shock": {
        "rates_sensitivity": -2.5,
        "growth_factor": -2.0,
        "market_beta": -1.5,
    },
    "stagflation_2x_macro": {
        "rates_sensitivity": -2.0,
        "commodities": 2.5,
        "growth_factor": -2.0,
        "market_beta": -1.5,
    },
}


def list_scenarios() -> list[str]:
    """Return registered stress scenario names (for the dashboard dropdown)."""
    return list(STRESS_SCENARIOS.keys())


def _robust_cov(X: np.ndarray) -> np.ndarray:
    """Shared robust-covariance helper.

    Prefers MCD when the obs/feature ratio supports it; otherwise falls
    back to Ledoit-Wolf shrinkage.
    """
    # TODO: consider shared robust_cov utility after Phase 12
    n_obs, n_feat = X.shape
    if n_obs >= MCD_MIN_OBS_PER_FEATURE * n_feat and n_obs > n_feat + 1:
        try:
            est = MinCovDet().fit(X)
            return est.covariance_
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("mcd_failed_fallback", error=str(exc))
    return LedoitWolf().fit(X).covariance_


def _crisis_mask(index: pd.DatetimeIndex) -> np.ndarray:
    mask = np.zeros(len(index), dtype=bool)
    for start, end in CRISIS_WINDOWS:
        s = pd.Timestamp(start)
        e = pd.Timestamp(end)
        mask |= (index >= s) & (index <= e)
    return mask


def fit_two_regime_covariance(
    returns: pd.DataFrame,
) -> dict[str, np.ndarray]:
    """Fit normal-regime and stressed-regime robust covariance matrices.

    ``returns`` must be indexed by date and have one column per ticker.
    """
    if not isinstance(returns.index, pd.DatetimeIndex):
        returns = returns.copy()
        returns.index = pd.to_datetime(returns.index)
    mask = _crisis_mask(returns.index)
    normal = returns.loc[~mask].dropna(how="any").to_numpy()
    crisis = returns.loc[mask].dropna(how="any").to_numpy()

    if normal.size == 0:
        raise ValueError("No normal-regime data available")

    normal_cov = _robust_cov(normal)

    if crisis.shape[0] < MCD_MIN_OBS_PER_FEATURE * crisis.shape[1] if crisis.size else True:
        logger.warning(
            "stressed_cov_using_raw_data",
            n_obs=int(crisis.shape[0]) if crisis.size else 0,
            n_feat=int(crisis.shape[1]) if crisis.size else 0,
        )
        if crisis.size and crisis.shape[0] >= 2:
            crisis_cov = np.cov(crisis, rowvar=False)
        else:
            # Fall back to scaled normal-regime covariance with a stress
            # multiplier so the matrix remains PSD.
            crisis_cov = 2.0 * normal_cov
    else:
        crisis_cov = _robust_cov(crisis)

    return {"normal_cov": normal_cov, "stressed_cov": crisis_cov}


def run_stress_test(
    scenario_name: str,
    portfolio_weights: np.ndarray,
    portfolio_betas: dict[str, float],
    covariance_dict: dict[str, np.ndarray],
    factor_vols: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Apply a named scenario to the current portfolio.

    Parameters
    ----------
    portfolio_betas:
        Aggregated factor beta — typically ``sum_i w_i * beta_i``.
    factor_vols:
        Optional one-σ daily move in each factor.  Defaults to 1% if not
        supplied (scenario shocks are in σ units).
    """
    if scenario_name not in STRESS_SCENARIOS:
        raise KeyError(f"Unknown scenario: {scenario_name}")
    scenario = STRESS_SCENARIOS[scenario_name]
    vols = factor_vols or {}

    factor_impact = 0.0
    contributions: dict[str, float] = {}
    for factor, shock_sigma in scenario.items():
        beta = float(portfolio_betas.get(factor, 0.0))
        factor_sigma = float(vols.get(factor, 0.01))
        contribution = beta * shock_sigma * factor_sigma
        factor_impact += contribution
        contributions[factor] = contribution

    stressed_cov = covariance_dict["stressed_cov"]
    stressed_vol = float(
        np.sqrt(max(portfolio_weights @ stressed_cov @ portfolio_weights, 0.0))
    )

    return {
        "scenario": scenario_name,
        "factor_impact": factor_impact,
        "factor_contributions": contributions,
        "stressed_vol": stressed_vol,
        "note": STRESS_NOTE,
    }
