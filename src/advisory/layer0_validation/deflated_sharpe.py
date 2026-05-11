"""Deflated Sharpe Ratio (Bailey & Lopez de Prado, 2014).

The DSR adjusts an observed Sharpe for (a) the number of trials that have
been run on the underlying universe and (b) the non-normality of returns.
The trial count is read from the :class:`AuditLog` so it cannot be
silently understated by the caller.
"""
from __future__ import annotations

import math
from typing import Any

import structlog
from scipy.stats import norm

from .audit_log import AuditLog

logger = structlog.get_logger(__name__)

STATIC_TRIAL_FLOOR: int = 2000
"""Architectural floor: ``n_trials = max(audit_count, STATIC_TRIAL_FLOOR)``."""

_EULER_MASCHERONI = 0.5772156649015329


def _expected_max_sharpe(n_trials: int) -> float:
    """Expected maximum of ``n_trials`` independent N(0,1) draws.

    Closed-form Bailey & Lopez de Prado approximation.
    """
    if n_trials <= 1:
        return 0.0
    z1 = norm.ppf(1 - 1.0 / n_trials)
    z2 = norm.ppf(1 - 1.0 / (n_trials * math.e))
    return (1 - _EULER_MASCHERONI) * z1 + _EULER_MASCHERONI * z2


def deflated_sharpe(
    observed_sharpe: float,
    skew: float,
    kurt: float,
    n_obs: int,
    audit_log: AuditLog,
) -> dict[str, Any]:
    """Compute the deflated Sharpe ratio.

    Parameters
    ----------
    observed_sharpe:
        Annualised observed Sharpe.
    skew, kurt:
        Sample skewness and *excess* kurtosis of the return series.
    n_obs:
        Number of return observations the Sharpe was computed over.
    audit_log:
        The audit log.  ``trial_count()`` is read internally so the caller
        cannot accidentally pass a smaller value.
    """
    audit_trial_count = audit_log.trial_count()
    n_trials = max(audit_trial_count, STATIC_TRIAL_FLOOR)

    expected_max = _expected_max_sharpe(n_trials)

    # Variance of estimated Sharpe under non-normality
    # (Bailey & Lopez de Prado equation):
    #   var(SR_hat) = (1 - skew * SR + (kurt-1)/4 * SR^2) / (n_obs - 1)
    if n_obs <= 1:
        dsr = 0.0
        z = 0.0
    else:
        var_sr = (
            1.0 - skew * observed_sharpe + ((kurt - 1.0) / 4.0) * observed_sharpe**2
        ) / (n_obs - 1)
        var_sr = max(var_sr, 1e-12)
        z = (observed_sharpe - expected_max) / math.sqrt(var_sr)
        dsr = float(norm.cdf(z))

    result = {
        "deflated_sharpe": dsr,
        "observed_sharpe": observed_sharpe,
        "expected_max_under_null": expected_max,
        "n_trials_used": n_trials,
        "audit_trial_count": audit_trial_count,
        "static_trial_floor": STATIC_TRIAL_FLOOR,
        "z_statistic": z,
    }
    logger.info("deflated_sharpe", **result)
    return result
