"""Conditional expectancy table.

Reports forward-return statistics conditioned on five named market
states.  These labels are displayed verbatim on the dashboard.
"""
from __future__ import annotations

import numpy as np
import polars as pl

CONDITION_LABELS: tuple[str, ...] = (
    "Calm bull",
    "Volatile bull",
    "Mean-reverting chop",
    "Volatile bear",
    "Stressed bear",
)

MIN_OBS_PER_CONDITION: int = 10


def _classify(vix_pct: float, ret_21d: float) -> str | None:
    """Bucket an observation into one of five labels (or None if borderline)."""
    if vix_pct < 0.33 and ret_21d > 0.01:
        return "Calm bull"
    if vix_pct >= 0.33 and vix_pct < 0.66 and ret_21d > 0.01:
        return "Volatile bull"
    if abs(ret_21d) <= 0.01:
        return "Mean-reverting chop"
    if vix_pct >= 0.66 and ret_21d <= -0.01:
        return "Stressed bear"
    if ret_21d <= -0.01:
        return "Volatile bear"
    return None


def build_conditional_expectancy_table(
    feature_history: pl.DataFrame,
    forward_return_col: str = "ret_fwd_10d",
    vix_col: str = "vix_percentile_63d",
    state_col: str = "ret_21d",
) -> pl.DataFrame:
    """One row per named condition; columns: mean, median, hit_rate, n_obs."""
    required = {forward_return_col, vix_col, state_col}
    missing = required - set(feature_history.columns)
    if missing:
        raise ValueError(f"feature_history missing columns: {sorted(missing)}")

    df = feature_history.select([forward_return_col, vix_col, state_col]).drop_nulls()
    if df.height == 0:
        return pl.DataFrame(
            schema={
                "condition": pl.Utf8,
                "n_obs": pl.Int64,
                "mean_fwd_return": pl.Float64,
                "median_fwd_return": pl.Float64,
                "hit_rate": pl.Float64,
            }
        )

    labels: list[str | None] = [
        _classify(v, r) for v, r in zip(df[vix_col].to_list(), df[state_col].to_list())
    ]
    df = df.with_columns(pl.Series(name="__cond__", values=labels))

    rows: list[dict] = []
    for label in CONDITION_LABELS:
        sub = df.filter(pl.col("__cond__") == label)
        n = sub.height
        if n < MIN_OBS_PER_CONDITION:
            continue
        returns = sub[forward_return_col].to_numpy()
        rows.append(
            {
                "condition": label,
                "n_obs": int(n),
                "mean_fwd_return": float(np.mean(returns)),
                "median_fwd_return": float(np.median(returns)),
                "hit_rate": float(np.mean(returns > 0)),
            }
        )
    return pl.DataFrame(rows) if rows else pl.DataFrame(
        schema={
            "condition": pl.Utf8,
            "n_obs": pl.Int64,
            "mean_fwd_return": pl.Float64,
            "median_fwd_return": pl.Float64,
            "hit_rate": pl.Float64,
        }
    )
