"""Find empirically validated contradictions between developer-specified
feature pairs (Layer 7).

The function name ``find_validated_contradictions`` is intentional —
the architecture explicitly rejects the misleading "data-driven" label.
The contradiction pairs are fixed by the architecture; adding pairs is
a hypothesis-test addition and requires DSR re-computation.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import polars as pl
import structlog
from scipy.stats import fisher_exact

logger = structlog.get_logger(__name__)


CONTRADICTION_PAIRS: list[tuple[str, str]] = [
    ("momentum_norm",       "breadth_pct_above_ma50_norm"),
    ("prob_positive_10d",   "realized_vol_percentile_norm"),
    ("earnings_revision_z", "hy_spread_roc_21d_norm"),
    ("earnings_revision_z", "rsi_14_norm"),
]


CONTRADICTION_LABEL: str = (
    "data-validated contradiction "
    "(developer-specified pair, empirically confirmed)"
)


DEFAULT_SIGNIFICANCE: float = 0.01  # tighter than 0.05 because pairs are pre-specified
MIN_N_EACH_CELL: int = 20


def _outcome_bucket(values: np.ndarray, *, high: bool) -> np.ndarray:
    """Return a boolean mask of upper-half (``high=True``) or lower-half rows."""
    median = np.nanmedian(values)
    return values > median if high else values < median


def find_validated_contradictions(
    feature_history: pl.DataFrame,
    forward_return_col: str = "ret_fwd_10d",
    pairs: list[tuple[str, str]] | None = None,
    significance: float = DEFAULT_SIGNIFICANCE,
    min_n_each_cell: int = MIN_N_EACH_CELL,
) -> list[dict[str, Any]]:
    """For each developer-specified pair, test whether the joint-high regime
    has a materially different hit rate from the joint-low regime.
    """
    pairs = pairs or CONTRADICTION_PAIRS
    if forward_return_col not in feature_history.columns:
        return []

    fwd = feature_history[forward_return_col].to_numpy()
    hits = (fwd > 0).astype(int)

    results: list[dict[str, Any]] = []
    for feat_a, feat_b in pairs:
        if feat_a not in feature_history.columns or feat_b not in feature_history.columns:
            logger.debug("contradiction_pair_skipped_missing_column", a=feat_a, b=feat_b)
            continue
        a = feature_history[feat_a].to_numpy()
        b = feature_history[feat_b].to_numpy()
        mask_a_hi = _outcome_bucket(a, high=True)
        mask_b_hi = _outcome_bucket(b, high=True)
        mask_a_lo = _outcome_bucket(a, high=False)
        mask_b_lo = _outcome_bucket(b, high=False)
        joint_hi = mask_a_hi & mask_b_hi
        joint_lo = mask_a_lo & mask_b_lo
        if joint_hi.sum() < min_n_each_cell or joint_lo.sum() < min_n_each_cell:
            logger.debug(
                "contradiction_pair_skipped_cell_too_small",
                a=feat_a,
                b=feat_b,
                n_hi=int(joint_hi.sum()),
                n_lo=int(joint_lo.sum()),
            )
            continue
        hi_hits = int(hits[joint_hi].sum())
        hi_miss = int(joint_hi.sum() - hi_hits)
        lo_hits = int(hits[joint_lo].sum())
        lo_miss = int(joint_lo.sum() - lo_hits)
        table = [[hi_hits, hi_miss], [lo_hits, lo_miss]]
        try:
            _, p_value = fisher_exact(table)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("fisher_exact_failed", a=feat_a, b=feat_b, error=str(exc))
            continue
        if p_value > significance:
            continue
        hi_rate = hi_hits / max(hi_hits + hi_miss, 1)
        lo_rate = lo_hits / max(lo_hits + lo_miss, 1)
        results.append(
            {
                "feature_a": feat_a,
                "feature_b": feat_b,
                "label": CONTRADICTION_LABEL,
                "joint_high_hit_rate": float(hi_rate),
                "joint_low_hit_rate": float(lo_rate),
                "p_value": float(p_value),
                "n_high": int(joint_hi.sum()),
                "n_low": int(joint_lo.sum()),
                "alert_type": "contradiction",
            }
        )
    return results
