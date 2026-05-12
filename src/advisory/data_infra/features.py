"""Compute the system's per-ticker features from OHLCV.

The computations live here so both the synthetic seed and the real-data
ingest path produce *exactly* the same feature schema.  All features
are written into ``features_pit`` via :meth:`FeatureStore.write_features`.
"""
from __future__ import annotations

from datetime import date
from typing import Iterable

import numpy as np
import polars as pl
import structlog

logger = structlog.get_logger(__name__)


# Trading-day windows used below.  Pinned constants — change them only
# alongside a corresponding update to FEATURE_HALFLIVES and the
# validation thresholds.
RET_WINDOWS: tuple[int, ...] = (1, 5, 21, 63)
VOL_WINDOW: int = 21
RSI_WINDOW: int = 14
MA_WINDOW: int = 50
FORWARD_WINDOW: int = 10

ANNUALISATION: float = float(np.sqrt(252))


def _rsi(close: pl.Series, window: int = RSI_WINDOW) -> pl.Series:
    """Standard Wilder RSI on close prices."""
    delta = close.diff()
    gain = delta.clip(lower_bound=0.0).fill_null(0.0)
    loss = (-delta).clip(lower_bound=0.0).fill_null(0.0)
    # Smoothed (Wilder) moving averages via EWM with alpha=1/window.
    avg_gain = gain.ewm_mean(alpha=1.0 / window, adjust=False)
    avg_loss = loss.ewm_mean(alpha=1.0 / window, adjust=False)
    rs = avg_gain / avg_loss.fill_null(0.0).clip(lower_bound=1e-12)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi


def compute_ohlcv_features(ohlcv: pl.DataFrame) -> pl.DataFrame:
    """Turn an OHLCV frame into the per-ticker feature rows we store.

    Input columns required: ``ticker``, ``effective_date``, ``close``,
    optionally ``high`` / ``low`` / ``volume``.

    Output: long-format ``(ticker, effective_date, knowledge_date,
    feature_name, feature_value)`` rows ready for
    :meth:`FeatureStore.write_features`.
    """
    required = {"ticker", "effective_date", "close"}
    missing = required - set(ohlcv.columns)
    if missing:
        raise ValueError(f"compute_ohlcv_features missing columns: {sorted(missing)}")

    rows: list[pl.DataFrame] = []
    for ticker, group in ohlcv.sort(["ticker", "effective_date"]).group_by(
        "ticker", maintain_order=True
    ):
        tk = ticker[0] if isinstance(ticker, tuple) else ticker
        df = group.sort("effective_date")
        close = df["close"]
        dates = df["effective_date"]

        # Multi-window returns
        log_close = np.log(close.to_numpy().astype(float))
        for w in RET_WINDOWS:
            if len(log_close) <= w:
                continue
            ret = np.full(len(log_close), np.nan)
            ret[w:] = np.exp(log_close[w:] - log_close[:-w]) - 1.0
            rows.append(
                _long(
                    ticker=tk,
                    dates=dates,
                    feature=f"ret_{w}d",
                    values=ret,
                )
            )

        # Realized vol (annualised, daily-log basis)
        daily_log = np.full(len(log_close), np.nan)
        daily_log[1:] = log_close[1:] - log_close[:-1]
        rv = (
            pl.Series(daily_log)
            .rolling_std(window_size=VOL_WINDOW, min_samples=VOL_WINDOW)
            .to_numpy()
            * ANNUALISATION
        )
        rows.append(_long(tk, dates, f"realized_vol_{VOL_WINDOW}d", rv))

        # RSI
        rsi = _rsi(close).to_numpy()
        rows.append(_long(tk, dates, "rsi_14", rsi))

        # % above MA50 — boolean as float so feature_value stays DOUBLE
        ma = close.rolling_mean(window_size=MA_WINDOW, min_samples=MA_WINDOW).to_numpy()
        above = (close.to_numpy() > ma).astype(float)
        above = np.where(np.isnan(ma), np.nan, above)
        rows.append(_long(tk, dates, "pct_above_ma50", above))

        # Forward return (label) — leaked feature, used by Layer 2's
        # analog engine and downstream sizing diagnostics
        fwd = np.full(len(log_close), np.nan)
        if len(log_close) > FORWARD_WINDOW:
            fwd[:-FORWARD_WINDOW] = (
                np.exp(log_close[FORWARD_WINDOW:] - log_close[:-FORWARD_WINDOW]) - 1.0
            )
        rows.append(_long(tk, dates, f"ret_fwd_{FORWARD_WINDOW}d", fwd))

    if not rows:
        return _empty_features()
    combined = pl.concat(rows).drop_nulls(subset=["feature_value"])
    return combined


def _long(
    ticker: str,
    dates: pl.Series,
    feature: str,
    values: np.ndarray | list[float],
) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "ticker": [ticker] * len(values),
            "effective_date": dates.to_list(),
            "knowledge_date": dates.to_list(),
            "feature_name": [feature] * len(values),
            "feature_value": [
                float(v) if v is not None and np.isfinite(v) else None for v in values
            ],
        },
        schema={
            "ticker": pl.Utf8,
            "effective_date": pl.Date,
            "knowledge_date": pl.Date,
            "feature_name": pl.Utf8,
            "feature_value": pl.Float64,
        },
    )


def _empty_features() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "ticker": pl.Utf8,
            "effective_date": pl.Date,
            "knowledge_date": pl.Date,
            "feature_name": pl.Utf8,
            "feature_value": pl.Float64,
        }
    )


def vix_percentile_from_close(
    vix_close: pl.DataFrame,
    window: int = 63,
) -> pl.DataFrame:
    """Compute ``vix_percentile_63d`` from a VIX OHLCV frame.

    Input: any frame with ``effective_date`` and ``close`` (VIX index level).
    Output: long-format feature rows for ticker ``"^VIX"``.
    """
    if vix_close.is_empty():
        return _empty_features()
    df = vix_close.sort("effective_date")
    closes = df["close"].to_numpy().astype(float)
    pct = np.full(len(closes), np.nan)
    for i in range(window, len(closes)):
        win = closes[i - window : i]
        pct[i] = float(np.mean(closes[i] >= win))
    return _long("^VIX", df["effective_date"], f"vix_percentile_{window}d", pct)


def yield_curve_slope(
    dgs10: pl.DataFrame,
    dgs2: pl.DataFrame,
) -> pl.DataFrame:
    """Compute ``yield_curve_slope = DGS10 - DGS2`` as a macro feature."""
    if dgs10.is_empty() or dgs2.is_empty():
        return _empty_features()
    a = dgs10.rename({"value": "y10"}).select(["effective_date", "y10"])
    b = dgs2.rename({"value": "y2"}).select(["effective_date", "y2"])
    j = a.join(b, on="effective_date", how="inner").with_columns(
        (pl.col("y10") - pl.col("y2")).alias("slope")
    )
    return _long(
        ticker="MACRO",
        dates=j["effective_date"],
        feature="yield_curve_slope",
        values=j["slope"].to_numpy(),
    )


def hy_spread_roc(
    hy_spread: pl.DataFrame,
    window: int = 21,
) -> pl.DataFrame:
    """Rate-of-change of the HY OAS over ``window`` trading days."""
    if hy_spread.is_empty():
        return _empty_features()
    df = hy_spread.sort("effective_date")
    values = df["value"].to_numpy().astype(float)
    roc = np.full(len(values), np.nan)
    if len(values) > window:
        roc[window:] = (values[window:] - values[:-window]) / np.maximum(
            np.abs(values[:-window]), 1e-9
        )
    return _long(
        ticker="MACRO",
        dates=df["effective_date"],
        feature=f"hy_spread_roc_{window}d",
        values=roc,
    )


__all__ = [
    "ANNUALISATION",
    "FORWARD_WINDOW",
    "MA_WINDOW",
    "RET_WINDOWS",
    "RSI_WINDOW",
    "VOL_WINDOW",
    "compute_ohlcv_features",
    "hy_spread_roc",
    "vix_percentile_from_close",
    "yield_curve_slope",
]
