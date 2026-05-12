"""FDR-corrected alert filtering + severity-ranked top-K.

Benjamini-Yekutieli (BY) correction is used throughout this module.
BH (Benjamini-Hochberg) controls FDR only under independence or positive
regression dependency. Financial features have complex, time-varying,
sometimes strongly negative cross-correlations — BY's arbitrary-dependence
guarantee is required. BY is more conservative than BH; this is correct.
"""
from __future__ import annotations

from typing import Any

import structlog
from statsmodels.stats.multitest import multipletests

logger = structlog.get_logger(__name__)


SEVERITY_SCORES: dict[str, int] = {
    "contradiction":       3,
    "factor_redundancy":   2,
    "regime_disagreement": 3,
    "friction_anomaly":    1,
    "transition_signal":   2,
}

DEFAULT_FDR_ALPHA: float = 0.05


def apply_fdr_correction(
    alerts: list[dict[str, Any]],
    alpha: float = DEFAULT_FDR_ALPHA,
) -> list[dict[str, Any]]:
    """Apply Benjamini-Yekutieli FDR correction to any alert with a p-value.

    Alerts without a ``p_value`` pass through untouched.
    """
    if not alerts:
        return []

    with_p = [a for a in alerts if "p_value" in a]
    without_p = [a for a in alerts if "p_value" not in a]
    if not with_p:
        return alerts

    p_values = [a["p_value"] for a in with_p]
    reject, p_corr, _, _ = multipletests(p_values, alpha=alpha, method="fdr_by")
    survivors: list[dict[str, Any]] = []
    for alert, keep, pc in zip(with_p, reject, p_corr):
        if not keep:
            continue
        new = dict(alert)
        new["p_value_corrected"] = float(pc)
        new["fdr_method"] = "fdr_by"
        survivors.append(new)
    return survivors + without_p


def filter_top_k_alerts(
    alerts: list[dict[str, Any]], k: int
) -> list[dict[str, Any]]:
    """Sort alerts by severity desc (and by ``p_value_corrected`` asc as
    tie-breaker for alerts with statistics).  Return the top-K.
    """

    def _key(a: dict[str, Any]) -> tuple[int, float]:
        sev = SEVERITY_SCORES.get(a.get("alert_type", ""), 0)
        p = float(a.get("p_value_corrected", a.get("p_value", 1.0)))
        # Sort descending on severity (use -sev) then ascending on p.
        return (-sev, p)

    return sorted(alerts, key=_key)[:k]
