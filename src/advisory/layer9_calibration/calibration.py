"""Trader calibration system.

Spearman rank correlation detects monotonic order, not calibration.
A trader who is uniformly overconfident at every confidence level can still
produce a positive Spearman; the reliability diagram catches this immediately.
This module uses the standard calibration measures: reliability diagram,
Brier score, and Expected Calibration Error.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import polars as pl
import structlog

logger = structlog.get_logger(__name__)


ECE_WELL_CALIBRATED: float = 0.05
ECE_MODERATE: float = 0.10
MIN_ENTRIES: int = 15
THESIS_DRIFT_THRESHOLD: int = 3


# Architecture-pinned conversion: confidence 1-5 → implied probability bucket.
CONFIDENCE_TO_PROB: dict[int, float] = {
    1: 0.30,
    2: 0.45,
    3: 0.55,
    4: 0.70,
    5: 0.85,
}


class TraderCalibrationSystem:
    """Reliability diagram + Brier + ECE + regime stats + drift detection."""

    def _entries_dataframe(self, journal: pl.DataFrame) -> pl.DataFrame | None:
        if journal is None or journal.height == 0:
            return None
        required = {"confidence_self", "pnl_pct"}
        if not required.issubset(set(journal.columns)):
            return None
        df = journal.filter(pl.col("pnl_pct").is_not_null())
        df = df.filter(pl.col("confidence_self").is_not_null())
        return df

    @staticmethod
    def _wilson_score(
        wins: int, n: int, z: float = 1.96
    ) -> tuple[float, float]:
        """Wilson score CI for a binomial proportion.  ``n=0 → (0, 1)``."""
        if n <= 0:
            return 0.0, 1.0
        phat = wins / n
        denom = 1.0 + z**2 / n
        centre = (phat + z**2 / (2 * n)) / denom
        margin = (z * math.sqrt(phat * (1 - phat) / n + z**2 / (4 * n**2))) / denom
        return max(0.0, centre - margin), min(1.0, centre + margin)

    # --- public surface ---------------------------------------------------

    def evaluate(self, journal: pl.DataFrame) -> dict[str, Any]:
        df = self._entries_dataframe(journal)
        if df is None or df.height < MIN_ENTRIES:
            return {
                "status": "INSUFFICIENT_DATA",
                "n_entries": int(df.height) if df is not None else 0,
                "min_required": MIN_ENTRIES,
            }

        confidence = df["confidence_self"].cast(pl.Int64).to_numpy()
        pnl = df["pnl_pct"].cast(pl.Float64).to_numpy()
        wins = (pnl > 0).astype(int)
        predicted = np.array([CONFIDENCE_TO_PROB[int(c)] for c in confidence])

        # Reliability diagram per confidence level
        reliability: list[dict[str, Any]] = []
        ece = 0.0
        n_total = len(predicted)
        for c in sorted(set(confidence.tolist())):
            mask = confidence == c
            n_c = int(mask.sum())
            if n_c == 0:
                continue
            avg_pred = float(predicted[mask].mean())
            avg_obs = float(wins[mask].mean())
            ci_lo, ci_hi = self._wilson_score(int(wins[mask].sum()), n_c)
            ece += (n_c / n_total) * abs(avg_pred - avg_obs)
            reliability.append(
                {
                    "confidence": int(c),
                    "n": n_c,
                    "avg_predicted": avg_pred,
                    "avg_observed": avg_obs,
                    "ci_low": ci_lo,
                    "ci_high": ci_hi,
                }
            )

        brier = float(np.mean((predicted - wins) ** 2))

        if ece < ECE_WELL_CALIBRATED:
            band = "well_calibrated"
        elif ece < ECE_MODERATE:
            band = "moderately_calibrated"
        else:
            band = "poorly_calibrated"

        return {
            "status": "OK",
            "n_entries": int(n_total),
            "reliability": reliability,
            "brier": brier,
            "ece": float(ece),
            "calibration_band": band,
        }

    def compute_regime_performance(
        self, journal: pl.DataFrame
    ) -> dict[str, Any]:
        df = self._entries_dataframe(journal)
        if df is None or df.height == 0:
            return {"status": "INSUFFICIENT_DATA", "regimes": {}}
        if "market_state_id" not in df.columns:
            return {"status": "INSUFFICIENT_DATA", "regimes": {}}
        n_null = df.filter(pl.col("market_state_id").is_null()).height
        if n_null:
            logger.warning(
                "regime_perf_skipping_null_states", n_excluded=n_null
            )
        df = df.filter(pl.col("market_state_id").is_not_null())
        regimes: dict[int, dict[str, float]] = {}
        for s in sorted(set(df["market_state_id"].to_list())):
            sub = df.filter(pl.col("market_state_id") == s)
            pnl = sub["pnl_pct"].cast(pl.Float64).to_numpy()
            if pnl.size == 0:
                continue
            regimes[int(s)] = {
                "n": int(pnl.size),
                "hit_rate": float((pnl > 0).mean()),
                "mean_pnl_pct": float(pnl.mean()),
            }
        return {"status": "OK", "regimes": regimes}

    def detect_thesis_drift(self, journal: pl.DataFrame) -> dict[str, Any]:
        df = self._entries_dataframe(journal)
        if df is None or "thesis_validated" not in df.columns:
            return {"warning": False, "n_invalidated_losses": 0}
        drift = df.filter(
            (pl.col("thesis_validated") == False)  # noqa: E712
            & (pl.col("pnl_pct") < 0)
        )
        n = int(drift.height)
        return {
            "warning": n > THESIS_DRIFT_THRESHOLD,
            "n_invalidated_losses": n,
            "threshold": THESIS_DRIFT_THRESHOLD,
        }
