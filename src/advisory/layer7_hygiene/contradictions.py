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


# V7_lite status taxonomy.  Each contradiction pair carries one of
# these status strings; the dashboard surfaces the matching message.
CONTRADICTION_STATUS: dict[str, str] = {
    "VALIDATED": (
        "Statistical test passed BY-FDR gate (developer-specified pair, "
        "empirically confirmed). Treat as a data-validated contradiction."
    ),
    "HEURISTIC": (
        "Heuristic rule — not system-derived. Apply additional caution."
    ),
    "UNTESTABLE_LITE": (
        "Feature unavailable in V7_lite (requires Sharadar PIT data). "
        "This pair cannot be tested in the current data environment. "
        "It may be a real contradiction — it cannot be confirmed or denied."
    ),
    "INSUFFICIENT_DATA": (
        "Cell count below minimum threshold on available features."
    ),
}

# Features absent from the V7_lite data tier — any contradiction pair
# referencing one of these is marked UNTESTABLE_LITE instead of being
# silently dropped.
LITE_NULL_FEATURES: frozenset[str] = frozenset(
    {"earnings_revision_z", "analyst_upgrade_z"}
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
    app_mode: str = "v7_institutional",
) -> list[dict[str, Any]]:
    """For each developer-specified pair, test whether the joint-high regime
    has a materially different hit rate from the joint-low regime.

    In ``app_mode == "v7_lite"``, any pair containing a feature from
    :data:`LITE_NULL_FEATURES` is emitted with status ``UNTESTABLE_LITE``
    rather than being silently dropped — architectural invariant.
    """
    pairs = pairs or CONTRADICTION_PAIRS
    if forward_return_col not in feature_history.columns:
        # Even when the forward-return column is missing, lite mode still
        # surfaces the untestable pairs.  Institutional silently returns
        # empty (legacy contract).
        if app_mode == "v7_lite":
            return _untestable_lite_rows(pairs)
        return []

    fwd = feature_history[forward_return_col].to_numpy()
    hits = (fwd > 0).astype(int)

    results: list[dict[str, Any]] = []
    for feat_a, feat_b in pairs:
        if app_mode == "v7_lite" and (
            feat_a in LITE_NULL_FEATURES or feat_b in LITE_NULL_FEATURES
        ):
            results.append(_untestable_lite_row(feat_a, feat_b))
            continue
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


def _untestable_lite_row(feature_a: str, feature_b: str) -> dict[str, Any]:
    return {
        "feature_a": feature_a,
        "feature_b": feature_b,
        "label": "untestable in V7_lite",
        "status": "UNTESTABLE_LITE",
        "message": CONTRADICTION_STATUS["UNTESTABLE_LITE"],
        "alert_type": "contradiction",
    }


def _untestable_lite_rows(pairs: list[tuple[str, str]]) -> list[dict[str, Any]]:
    return [
        _untestable_lite_row(a, b)
        for a, b in pairs
        if a in LITE_NULL_FEATURES or b in LITE_NULL_FEATURES
    ]
