"""Macro factor proxies and sequential orthogonalisation.

The orthogonalisation processes factors in :data:`FACTOR_ORDER` exactly —
not sorted, not shuffled — so downstream betas are interpretable in a
stable hierarchy.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import structlog

logger = structlog.get_logger(__name__)


MACRO_FACTOR_PROXIES: dict[str, str] = {
    "market_beta":         "SPY",
    "rates_sensitivity":   "TLT",
    "credit_sensitivity":  "HYG",
    "growth_factor":       "QQQ",
    "value_factor":        "IWD",
    "small_cap":           "IWM",
    "usd_sensitivity":     "UUP",
    "commodities":         "DBC",
    "volatility_factor":   "SVXY",
    "semiconductor_cycle": "SMH",
}

FACTOR_ORDER: list[str] = list(MACRO_FACTOR_PROXIES.keys())

ZERO_VARIANCE_TOL: float = 1e-8


def orthogonalize_factors(factor_returns: pd.DataFrame) -> pd.DataFrame:
    """Sequentially residualise each factor against all prior factors.

    Order is :data:`FACTOR_ORDER`.  The first factor is unchanged.
    Near-zero-variance factors are passed through with a warning so the
    rest of the chain remains stable.
    """
    missing = [f for f in FACTOR_ORDER if f not in factor_returns.columns]
    if missing:
        raise ValueError(f"factor_returns missing factors: {missing}")

    out = pd.DataFrame(index=factor_returns.index, columns=FACTOR_ORDER, dtype=float)
    for i, name in enumerate(FACTOR_ORDER):
        col = factor_returns[name].astype(float).to_numpy()
        sd = np.nanstd(col, ddof=1)
        if sd < ZERO_VARIANCE_TOL:
            logger.warning("factor_near_zero_variance", factor=name, sd=sd)
            out[name] = col
            continue
        if i == 0:
            out[name] = col
            continue
        priors = out.iloc[:, :i].to_numpy()
        # Drop rows with any NaN in target or priors for the regression
        mask = np.isfinite(col) & np.all(np.isfinite(priors), axis=1)
        if mask.sum() < priors.shape[1] + 2:
            out[name] = col
            continue
        X = np.column_stack([np.ones(mask.sum()), priors[mask]])
        y = col[mask]
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        full_X = np.column_stack([np.ones(len(col)), priors])
        full_X[~np.isfinite(full_X)] = 0.0
        residual = col - full_X @ beta
        out[name] = residual

    return out
