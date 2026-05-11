"""Minimum knowledge-date lag for each feature, in trading days.

0 = real-time (close-of-day at effective_date)
1 = next-day available
3 = ~72 hour lag (earnings revision sources)
"""
from __future__ import annotations

FUNDAMENTAL_LAGS: dict[str, int] = {
    "earnings_revision_z":  3,
    "earnings_surprise_z":  3,
    "revenue_growth_yoy":   5,
    "pe_ratio_z":           1,
    "analyst_upgrade_z":    1,
    "vix_percentile_63d":   0,
    "hy_spread_roc_21d":    0,
    "ret_1d":               0,
    "ret_5d":               0,
    "ret_21d":              0,
    "ret_63d":              0,
    "realized_vol_21d":     0,
    "rsi_14":               0,
    "iv_rv_ratio":          0,
    "pct_above_ma50":       0,
    "yield_curve_slope":    0,
    "sector_relative_str":  0,
    "ret_fwd_10d":          0,
}


def get_lag(feature_name: str) -> int:
    """Return lag in trading days.  Unknown features default to 1 (conservative)."""
    return FUNDAMENTAL_LAGS.get(feature_name, 1)
