"""Tier 3 #7 — composite market-stress gauge.

A 0-100 stress read rolled up from real market-wide signals in ``features_pit``
(VIX percentile, HY-OAS momentum, cross-sectional realised vol, curve inversion)
with a **disclosed, fixed** weighting. This is presentation, not a validated
model — it always ships ``validated: false`` and shows its weights.
"""
from __future__ import annotations

from typing import Any

import duckdb
import numpy as np

# (feature_name, display, weight, invert) — invert=True means low value = stress.
_COMPONENTS = [
    ("vix_percentile_63d", "VIX percentile", 0.35, False, True),   # already a 0-1 percentile
    ("hy_spread_roc_21d", "HY-OAS momentum", 0.25, False, False),
    ("realized_vol_21d", "Realised vol (avg)", 0.25, False, False),
    ("yield_curve_slope", "Curve inversion", 0.15, True, False),
]

_LEVELS = [(25, "calm"), (50, "normal"), (75, "elevated"), (101, "stressed")]

_WEIGHTING_NOTE = (
    "heuristic — fixed weights (VIX 0.35, HY-OAS 0.25, realised vol 0.25, "
    "curve 0.15), not a validated model"
)


def _series(conn: duckdb.DuckDBPyConnection, feature_name: str) -> list[float]:
    rows = conn.execute(
        "SELECT effective_date, AVG(feature_value) FROM features_pit "
        "WHERE feature_name = ? GROUP BY effective_date ORDER BY effective_date",
        [feature_name],
    ).fetchall()
    return [float(r[1]) for r in rows if r[1] is not None]


def _pct_rank(values: list[float], latest: float) -> float:
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return 0.5
    return float((arr <= latest).mean())


def _level(composite: float) -> str:
    for hi, name in _LEVELS:
        if composite < hi:
            return name
    return "stressed"


def compute_stress(conn: duckdb.DuckDBPyConnection | None) -> dict[str, Any] | None:
    if conn is None:
        return None
    components: list[dict[str, Any]] = []
    weighted_sum = 0.0
    weight_total = 0.0
    for feature, display, weight, invert, already_pct in _COMPONENTS:
        series = _series(conn, feature)
        if len(series) < 30:
            continue
        latest = series[-1]
        pct = latest if already_pct else _pct_rank(series, latest)
        pct = float(np.clip(pct, 0.0, 1.0))
        if invert:
            pct = 1.0 - pct
        value100 = round(pct * 100, 1)
        components.append({"name": display, "value": value100, "weight": weight})
        weighted_sum += value100 * weight
        weight_total += weight

    if not components or weight_total == 0:
        return None
    composite = round(weighted_sum / weight_total, 1)
    return {
        "composite": composite,
        "level": _level(composite),
        "components": components,
        "weighting": _WEIGHTING_NOTE,
        "validated": False,
        "source": "live",
    }
