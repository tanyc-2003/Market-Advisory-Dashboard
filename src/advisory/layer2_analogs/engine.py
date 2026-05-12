"""Historical analog engine.

Finds the top-K most-similar past observations to a query state under a
shrinkage-stabilised Mahalanobis distance, with:

  * minimum-separation guard so very recent windows can't be chosen,
  * MCD fallback when the number of obs per feature is small,
  * recency-weighted effective N (logged),
  * dual-pass disagreement comparison (global vs within-state).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import numpy as np
import polars as pl
import structlog
from sklearn.covariance import LedoitWolf, MinCovDet

logger = structlog.get_logger(__name__)


MCD_MIN_OBS_PER_FEATURE: int = 20
"""Below this many obs/feature, MCD becomes unstable — fall back to shrinkage."""

RECENCY_HALF_LIFE_DAYS: int = 5 * 252
"""Half-life of recency weighting: ~5 trading years."""

DEFAULT_MIN_SEPARATION: int = 21
ABS_MIN_SEPARATION: int = 5

DISAGREEMENT_NOTE = (
    "Global and within-state analog sets disagree.  This means the current "
    "regime is unusual *given* the dominant HMM state — treat distribution "
    "estimates with caution."
)


@dataclass
class AnalogResult:
    indices: list[int]
    dates: list[date]
    distances: list[float]
    forward_returns: np.ndarray
    hit_rate: float
    effective_n_recency_weighted: float
    covariance_method: str
    state_filter: int | None


@dataclass
class DisagreementResult:
    overlap_pct: float
    global_set: AnalogResult
    within_state_set: AnalogResult
    note: str


@dataclass
class HistoricalAnalogEngine:
    feature_cols: list[str]
    friction_monitor: Any | None = None
    """Optional :class:`IntradayFrictionMonitor` injected by Layer 5.
    When provided, ``find_analogs`` reads ``friction_monitor.get_vol_z(ticker)``
    as the ``vol_z`` trigger for covariance cache invalidation.
    """
    cov_cache: dict = field(default_factory=dict, init=False, repr=False)

    def _fit_shrinkage_covariance(
        self, X: np.ndarray, anchor_date: date, vol_z: float = 0.0
    ) -> tuple[np.ndarray, str]:
        """Fit shrinkage covariance with vol-aware cache invalidation."""
        n_obs, n_feat = X.shape
        cache_key = (anchor_date, round(vol_z, 1))
        if cache_key in self.cov_cache:
            cov, method = self.cov_cache[cache_key]
            return cov, method

        if n_obs >= MCD_MIN_OBS_PER_FEATURE * n_feat:
            try:
                est = MinCovDet().fit(X)
                cov, method = est.covariance_, "mcd"
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning(
                    "mcd_failed_falling_back",
                    error=str(exc),
                    n_obs=n_obs,
                    n_feat=n_feat,
                )
                est = LedoitWolf().fit(X)
                cov, method = est.covariance_, "ledoit_wolf"
        else:
            logger.warning(
                "mcd_skipped_insufficient_obs",
                n_obs=n_obs,
                n_feat=n_feat,
                ratio=n_obs / max(n_feat, 1),
            )
            est = LedoitWolf().fit(X)
            cov, method = est.covariance_, "ledoit_wolf"

        self.cov_cache[cache_key] = (cov, method)
        return cov, method

    @staticmethod
    def _mahalanobis(X: np.ndarray, q: np.ndarray, cov: np.ndarray) -> np.ndarray:
        inv = np.linalg.pinv(cov)
        diff = X - q
        d2 = np.einsum("ij,jk,ik->i", diff, inv, diff)
        return np.sqrt(np.maximum(d2, 0.0))

    def find_analogs(
        self,
        feature_history: pl.DataFrame,
        query: np.ndarray,
        anchor_date: date,
        k: int = 30,
        min_separation: int = DEFAULT_MIN_SEPARATION,
        state_filter: int | None = None,
        vol_z: float = 0.0,
        forward_return_col: str = "ret_fwd_10d",
        ticker: str | None = None,
    ) -> AnalogResult:
        if min_separation < ABS_MIN_SEPARATION:
            raise ValueError(
                f"min_separation must be >= {ABS_MIN_SEPARATION}; got {min_separation}"
            )
        # If a friction monitor is wired in and the caller did not pass
        # an explicit vol_z, prefer the live read from Layer 5.
        if self.friction_monitor is not None and ticker is not None and vol_z == 0.0:
            try:
                vol_z = float(self.friction_monitor.get_vol_z(ticker))
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("friction_monitor_read_failed", error=str(exc))
        if forward_return_col not in feature_history.columns:
            raise ValueError(
                f"feature_history missing forward return column {forward_return_col!r}"
            )

        # 1. Filter by state if requested
        df = feature_history
        if state_filter is not None:
            if "hmm_state" not in df.columns:
                raise ValueError(
                    "state_filter set but feature_history has no `hmm_state` column"
                )
            df = df.filter(pl.col("hmm_state") == state_filter)

        # 2. Enforce minimum separation in time
        if "effective_date" not in df.columns:
            raise ValueError("feature_history must have `effective_date`")
        df = df.filter(pl.col("effective_date") < anchor_date)
        cutoff_idx = df.height
        # Drop the most recent min_separation rows
        if cutoff_idx > min_separation:
            df = df.slice(0, cutoff_idx - min_separation)
        else:
            df = df.slice(0, 0)

        if df.height == 0:
            return AnalogResult(
                indices=[],
                dates=[],
                distances=[],
                forward_returns=np.array([]),
                hit_rate=0.0,
                effective_n_recency_weighted=0.0,
                covariance_method="none",
                state_filter=state_filter,
            )

        X = df.select(self.feature_cols).to_numpy()
        cov, method = self._fit_shrinkage_covariance(X, anchor_date, vol_z=vol_z)
        distances = self._mahalanobis(X, np.asarray(query, dtype=float), cov)

        order = np.argsort(distances)[:k]
        chosen = df[order.tolist()]
        chosen_dates = chosen["effective_date"].to_list()
        chosen_returns = chosen[forward_return_col].to_numpy()
        chosen_distances = distances[order]

        # Recency-weighted effective N
        anchor_ordinal = anchor_date.toordinal()
        deltas = np.array(
            [(anchor_ordinal - d.toordinal()) for d in chosen_dates], dtype=float
        )
        weights = np.exp(-math.log(2) * deltas / RECENCY_HALF_LIFE_DAYS)
        if weights.sum() == 0:
            effective_n = 0.0
        else:
            effective_n = float(weights.sum() ** 2 / (weights**2).sum())
        logger.debug(
            "analog_effective_n",
            raw_n=len(order),
            effective_n=effective_n,
            covariance_method=method,
        )

        hit_rate = float((chosen_returns > 0).mean()) if chosen_returns.size else 0.0
        return AnalogResult(
            indices=[int(i) for i in order],
            dates=chosen_dates,
            distances=chosen_distances.tolist(),
            forward_returns=chosen_returns,
            hit_rate=hit_rate,
            effective_n_recency_weighted=effective_n,
            covariance_method=method,
            state_filter=state_filter,
        )

    def find_analogs_with_disagreement(
        self,
        feature_history: pl.DataFrame,
        query: np.ndarray,
        anchor_date: date,
        dominant_state_id: int,
        k: int = 30,
        min_separation: int = DEFAULT_MIN_SEPARATION,
        vol_z: float = 0.0,
        forward_return_col: str = "ret_fwd_10d",
    ) -> DisagreementResult:
        global_set = self.find_analogs(
            feature_history,
            query,
            anchor_date,
            k=k,
            min_separation=min_separation,
            state_filter=None,
            vol_z=vol_z,
            forward_return_col=forward_return_col,
        )
        within_state_set = self.find_analogs(
            feature_history,
            query,
            anchor_date,
            k=k,
            min_separation=min_separation,
            state_filter=dominant_state_id,
            vol_z=vol_z,
            forward_return_col=forward_return_col,
        )
        global_dates = set(global_set.dates)
        within_dates = set(within_state_set.dates)
        union = global_dates | within_dates
        overlap_pct = (
            len(global_dates & within_dates) / len(union) if union else 0.0
        )
        return DisagreementResult(
            overlap_pct=overlap_pct,
            global_set=global_set,
            within_state_set=within_state_set,
            note=DISAGREEMENT_NOTE if overlap_pct < 0.5 else "",
        )
