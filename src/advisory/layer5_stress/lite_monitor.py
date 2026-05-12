"""V7_lite friction monitor — Amihud + Corwin-Schultz.

**Critical separation** (architecture §11):

  ``amihud_z``                → Layer 5 anomaly score / alert trigger
  ``cs_spread_execution_proxy``→ Realistic Execution Harness fill-cost ONLY

Never combine them.  ``amihud_z`` is a price-impact measure; it spikes
during volatile, low-volume events — that is the value Layer 5 wants.
``cs_spread_execution_proxy`` is a half-spread estimate that we zero-
floor for the harness, which would *suppress* stress signal during
those exact volatile conditions.  See the docstrings on each function
and the harness assertion guard in Phase 12.

corwin_schultz_spread() returns NEGATIVE VALUES when overnight gap
variance exceeds intraday range.  Zero-flooring makes it usable for the
harness.  It would suppress stress Z-scores during volatile conditions —
do NOT use in Layer 5 anomaly detection.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import polars as pl
import structlog

logger = structlog.get_logger(__name__)


AMIHUD_DOLLAR_VOLUME_FLOOR: float = 1e4
"""Prevents division by near-zero on halted tickers."""


def amihud_illiquidity(
    close: np.ndarray,
    volume: np.ndarray,
) -> np.ndarray:
    """Amihud illiquidity = |log_return| / dollar_volume.

    Returns an array of length ``len(close) - 1`` (matching the log
    return length).  Strictly positive by construction; never floor at
    zero — strict positivity during volatile events is precisely what
    Layer 5 anomaly detection needs.

    Parameters
    ----------
    close, volume:
        Close prices and share volumes of equal length.
    """
    close_arr = np.asarray(close, dtype=float)
    volume_arr = np.asarray(volume, dtype=float)
    if close_arr.size != volume_arr.size:
        raise ValueError("close and volume must be the same length")
    if close_arr.size < 2:
        return np.array([], dtype=float)
    log_ret = np.diff(np.log(close_arr))
    dollar_vol = np.maximum(close_arr[1:] * volume_arr[1:], AMIHUD_DOLLAR_VOLUME_FLOOR)
    return np.abs(log_ret) / dollar_vol


def corwin_schultz_spread(
    high: np.ndarray,
    low: np.ndarray,
) -> np.ndarray:
    """Corwin-Schultz high-low half-spread estimator.

    Used ONLY for paper-trading harness fill-cost estimation.  Not used
    in Layer 5 stress detection.  See module docstring.

    Returns an array of length ``len(high) - 1`` (paired-bar estimator).
    Negative values from the closed-form CS solution are floored at 0.0
    because the harness consumes a half-spread cost, not a stress signal.
    """
    h = np.asarray(high, dtype=float)
    l = np.asarray(low, dtype=float)
    if h.size != l.size:
        raise ValueError("high and low must be the same length")
    if h.size < 2:
        return np.array([], dtype=float)

    # Two-day high-low estimator (Corwin & Schultz, 2012).
    beta = (np.log(h[:-1] / l[:-1])) ** 2 + (np.log(h[1:] / l[1:])) ** 2
    high_pair = np.maximum(h[:-1], h[1:])
    low_pair = np.minimum(l[:-1], l[1:])
    gamma = np.log(high_pair / np.maximum(low_pair, 1e-12)) ** 2
    sqrt2 = np.sqrt(2.0)
    alpha = (np.sqrt(2.0 * beta) - np.sqrt(beta)) / (3.0 - 2.0 * sqrt2) - np.sqrt(
        gamma / (3.0 - 2.0 * sqrt2)
    )
    spread = 2.0 * (np.exp(alpha) - 1.0) / (1.0 + np.exp(alpha))
    return np.maximum(spread, 0.0)


def _robust_z(series: np.ndarray) -> float:
    """Robust modified z-score of the last value (median + MAD)."""
    arr = series[np.isfinite(series)]
    if arr.size < 5:
        return 0.0
    median = float(np.nanmedian(arr))
    mad = float(np.nanmedian(np.abs(arr - median)))
    if mad == 0:
        return 0.0
    return (arr[-1] - median) * 0.6745 / mad


class LiteFrictionMonitor:
    """V7_lite Layer 5 stress monitor.

    Replaces :class:`IntradayFrictionMonitor` when ``APP_MODE == "v7_lite"``.
    Bid/ask spreads don't exist on yfinance daily bars, so:

    * Stress detection (the alert trigger) uses the **Amihud z-score**.
    * Fill-cost friction (consumed by
      :class:`RealisticExecutionHarness`) uses the **Corwin-Schultz**
      half-spread.

    Mixing them is forbidden by architecture and enforced by the harness
    assertion guard (Phase 12).
    """

    def __init__(self, economic_calendar: dict | None = None) -> None:
        self.economic_calendar = economic_calendar or {}
        self._latest_vol_z: dict[str, float] = {}

    def compute_friction_proxy(
        self,
        ticker: str,
        ohlcv_window: pl.DataFrame,
        on_date: date | None = None,
    ) -> dict[str, Any]:
        """Compute the two proxies for ``ticker`` from an OHLCV window.

        Returns a dict with both ``amihud_z`` and ``cs_spread_execution_proxy``
        as clearly separated fields.  The Layer 5 ``anomaly_score`` is
        derived from ``amihud_z`` only.
        """
        cols = ohlcv_window.columns
        for required in ("close", "high", "low", "volume"):
            if required not in cols:
                return {
                    "ticker": ticker,
                    "amihud_z": 0.0,
                    "cs_spread_execution_proxy": 0.0,
                    "anomaly_score": 0.0,
                    "status": "INSUFFICIENT_COLUMNS",
                }
        if ohlcv_window.height < 21:
            return {
                "ticker": ticker,
                "amihud_z": 0.0,
                "cs_spread_execution_proxy": 0.0,
                "anomaly_score": 0.0,
                "status": "INSUFFICIENT_DATA",
            }

        close = ohlcv_window["close"].to_numpy()
        vol = ohlcv_window["volume"].to_numpy()
        high = ohlcv_window["high"].to_numpy()
        low = ohlcv_window["low"].to_numpy()

        amihud = amihud_illiquidity(close, vol)
        cs = corwin_schultz_spread(high, low)

        amihud_z = _robust_z(amihud)
        cs_proxy = float(cs[-1]) if cs.size else 0.0

        anomaly_score = amihud_z  # ← Architectural invariant
        alert = abs(anomaly_score) >= 2.5

        self._latest_vol_z[ticker] = amihud_z

        return {
            "ticker": ticker,
            "amihud_z": float(amihud_z),
            "cs_spread_execution_proxy": float(cs_proxy),
            "anomaly_score": float(anomaly_score),
            "alert": bool(alert),
            "status": "OK",
            "on_date": on_date.isoformat() if on_date else None,
        }

    def get_vol_z(self, ticker: str) -> float:
        """Return the cached Amihud z-score for ``ticker``.

        This is what :class:`HistoricalAnalogEngine` reads for its
        covariance-cache invalidation trigger — and it is the **Amihud**
        value, never the Corwin-Schultz spread.
        """
        return float(self._latest_vol_z.get(ticker, 0.0))
