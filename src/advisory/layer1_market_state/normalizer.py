"""EWMA normalisation + the global ``EWMA_CLIP`` Winsorisation boundary.

The same ``EWMA_CLIP`` constant gates both this module and
:func:`~src.advisory.layer1_market_state.engine.winsorize`.  They must
not drift.
"""
from __future__ import annotations

import numpy as np
import polars as pl

from config.settings import settings

EWMA_CLIP: float = settings.ewma_clip

FEATURE_HALFLIVES: dict[str, int] = {
    "ret_1d":                5,
    "realized_vol_21d":     42,
    "hy_spread_roc_21d":    42,
    "vix_percentile_63d":   63,
    "yield_curve_slope":   126,
    "earnings_revision_z": 126,
    "pct_above_ma50":       42,
    "iv_rv_ratio":          21,
}

# V7_lite additional entries — additive only.  The V7 Institutional
# entries above are not modified.
FEATURE_HALFLIVES.update(
    {
        "hy_oas":                   63,
        "ig_oas":                   63,
        "sector_relative_ret_252d": 126,
        "vix_9d":                    5,
        "vix_1m":                   21,
        "vix_3m":                   42,
        "vix_term_slope":           21,
        "skew_index":               21,
        "put_call_ratio":           10,
        "ma_spread_50_200d":        42,
        "atr_pct_21d":              42,
        "pct_above_ma20":           21,
        "volume_norm_21d":          21,
        "treasury_10yr_roc_21d":    42,
        "rolling_sector_correlation_63d": 63,
    }
)

_DEFAULT_HALFLIFE: int = 63


def ewma_normalize(values: np.ndarray, half_life: int) -> np.ndarray:
    """Z-score ``values`` against an exponentially weighted mean/std.

    The output is clipped to ``[-EWMA_CLIP, EWMA_CLIP]`` so the same
    boundary applies in both training and inference.
    """
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return arr
    s = pl.Series(arr)
    mu = s.ewm_mean(half_life=half_life, adjust=False).to_numpy()
    var = s.ewm_var(half_life=half_life, adjust=False).to_numpy()
    sd = np.sqrt(np.where(var > 0, var, np.nan))
    z = (arr - mu) / sd
    z = np.where(np.isfinite(z), z, 0.0)
    return np.clip(z, -EWMA_CLIP, EWMA_CLIP)


def normalize_feature_matrix(
    df: pl.DataFrame, feature_cols: list[str]
) -> pl.DataFrame:
    """Apply :func:`ewma_normalize` to each named column in place (returned)."""
    out = df.clone()
    for col in feature_cols:
        if col not in out.columns:
            continue
        half_life = FEATURE_HALFLIVES.get(col, _DEFAULT_HALFLIFE)
        normalised = ewma_normalize(out[col].to_numpy(), half_life)
        out = out.with_columns(pl.Series(name=col, values=normalised))
    return out
