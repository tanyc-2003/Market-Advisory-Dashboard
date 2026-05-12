"""Intraday friction monitor — modified z-score of microstructure stress.

A robust z-score (median + MAD) detects spikes in spread, volume, and
realised volatility per ticker per bucketed time window.  Calendar
suppression silences alerts during scheduled macro events.
"""
from __future__ import annotations

from datetime import date, time as dtime
from typing import Any, Iterable

import numpy as np
import pandas as pd
import polars as pl
import structlog

from .calendar import CalendarEvent, is_suppression_active

logger = structlog.get_logger(__name__)


# 0.6745 ≈ Φ⁻¹(0.75); this makes 1.4826·MAD an unbiased estimator of σ
# under a Normal distribution.  It is the textbook scaling, not arbitrary.
MAD_TO_SIGMA: float = 0.6745
ALERT_Z_THRESHOLD: float = 2.5
MIN_BASELINE_OBS: int = 10

TIME_BUCKETS: tuple[str, ...] = (
    "open",     # 09:30 - 10:30
    "midday",   # 10:30 - 14:00
    "close",    # 14:00 - 16:00
    "after",    # after 16:00
)


def _to_bucket(t: Any) -> str:
    """Normalise ``t`` (str or ``datetime.time``) into one of TIME_BUCKETS."""
    if isinstance(t, dtime):
        hour = t.hour + t.minute / 60.0
    else:
        # Expect "HH:MM"
        h, m = str(t).split(":")
        hour = int(h) + int(m) / 60.0
    if hour < 10.5:
        return "open"
    if hour < 14.0:
        return "midday"
    if hour < 16.0:
        return "close"
    return "after"


class IntradayFrictionMonitor:
    """Compute friction z-scores and surface alerts unless suppressed."""

    def __init__(
        self,
        economic_calendar: dict[date, list[CalendarEvent]] | None = None,
        alert_threshold: float = ALERT_Z_THRESHOLD,
    ) -> None:
        self.economic_calendar = economic_calendar or {}
        self.alert_threshold = alert_threshold
        self._latest_vol_z: dict[str, float] = {}

    @staticmethod
    def _modified_z_score(values: np.ndarray, current: float) -> float:
        """Return the modified (MAD-based) z-score of ``current``."""
        median = float(np.nanmedian(values))
        mad = float(np.nanmedian(np.abs(values - median)))
        if mad == 0 or not np.isfinite(mad):
            return 0.0
        return (current - median) * MAD_TO_SIGMA / mad

    def get_vol_z(self, ticker: str) -> float:
        """Return the most recently computed volume z-score for ``ticker``.

        Consumed by :class:`HistoricalAnalogEngine` as the ``vol_z`` trigger
        for covariance-cache invalidation.
        """
        return float(self._latest_vol_z.get(ticker, 0.0))

    def compute_friction_z_score(
        self,
        ticker: str,
        on_date: date,
        bucket: str,
        current_observation: dict[str, float],
        baseline: pd.DataFrame,
    ) -> dict[str, Any]:
        """Compute z-scores for spread, volume, and realised vol.

        Parameters
        ----------
        baseline:
            Historical rows for this ticker / bucket.  Must contain
            columns ``spread_bps``, ``volume``, ``realized_vol``.
        """
        suppressed, reason = is_suppression_active(on_date, self.economic_calendar)
        if suppressed:
            logger.info(
                "friction_alert_suppressed",
                ticker=ticker,
                date=on_date.isoformat(),
                reason=reason,
            )
            return {"status": "SUPPRESSED", "reason": reason, "ticker": ticker}

        if bucket not in TIME_BUCKETS:
            raise ValueError(f"Unknown bucket {bucket!r}; expected one of {TIME_BUCKETS}")

        if baseline is None or baseline.shape[0] < MIN_BASELINE_OBS:
            return {
                "status": "INSUFFICIENT_DATA",
                "ticker": ticker,
                "n_baseline": int(baseline.shape[0]) if baseline is not None else 0,
            }

        spread_z = self._modified_z_score(
            baseline["spread_bps"].to_numpy(),
            float(current_observation["spread_bps"]),
        )
        volume_z = self._modified_z_score(
            baseline["volume"].to_numpy(),
            float(current_observation["volume"]),
        )
        rv_z = self._modified_z_score(
            baseline["realized_vol"].to_numpy(),
            float(current_observation["realized_vol"]),
        )
        max_z = max(abs(spread_z), abs(volume_z), abs(rv_z))
        alert = max_z >= self.alert_threshold

        self._latest_vol_z[ticker] = volume_z

        return {
            "status": "OK",
            "ticker": ticker,
            "date": on_date.isoformat(),
            "bucket": bucket,
            "spread_z": spread_z,
            "volume_z": volume_z,
            "realized_vol_z": rv_z,
            "max_abs_z": max_z,
            "alert": alert,
            "alert_threshold": self.alert_threshold,
        }


__all__ = [
    "ALERT_Z_THRESHOLD",
    "IntradayFrictionMonitor",
    "MAD_TO_SIGMA",
    "MIN_BASELINE_OBS",
    "TIME_BUCKETS",
    "_to_bucket",
]
