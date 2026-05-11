"""Market state engine: Winsorised Gaussian HMM, predictor-only.

``MarketStateEngine`` consumes a *fitted* HMM and surfaces:
  * state-probability vector for the current observation
  * dominant state id (argmax)
  * a binary ``transition_signal`` when uncertainty crosses the threshold

The HMM itself is fit by :func:`train_market_state_engine` so the
predictor surface never accidentally trains on inference-time data.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np
import polars as pl
import structlog
from hmmlearn import hmm

from ..layer0_validation.audit_log import AuditLog

logger = structlog.get_logger(__name__)


TRANSITION_UNCERTAINTY_THRESHOLD: float = 0.35


def winsorize(arr: np.ndarray, sigma_cap: float) -> np.ndarray:
    """Clip an array column-wise to ``[-sigma_cap, sigma_cap]`` standard deviations."""
    if arr.ndim != 2:
        raise ValueError(f"winsorize expects 2D array; got shape {arr.shape}")
    mu = np.nanmean(arr, axis=0, keepdims=True)
    sd = np.nanstd(arr, axis=0, ddof=1, keepdims=True)
    sd = np.where(sd > 0, sd, 1.0)
    z = (arr - mu) / sd
    z = np.clip(z, -sigma_cap, sigma_cap)
    return z * sd + mu


@dataclass
class StateObservation:
    state_probs: np.ndarray
    dominant_state_id: int
    state_uncertainty: float
    transition_signal: bool


@dataclass
class MarketStateEngine:
    hmm_model: Any
    feature_cols: list[str]
    sigma_cap: float = 4.0
    _training_mean: Optional[np.ndarray] = field(default=None, repr=False)
    _training_std: Optional[np.ndarray] = field(default=None, repr=False)

    def attach_training_moments(self, mu: np.ndarray, sd: np.ndarray) -> None:
        """Store the training mean/std so inference Winsorises identically."""
        self._training_mean = mu
        self._training_std = np.where(sd > 0, sd, 1.0)

    def _winsorize_inference(self, x: np.ndarray) -> np.ndarray:
        if self._training_mean is None or self._training_std is None:
            return winsorize(x, self.sigma_cap)
        z = (x - self._training_mean) / self._training_std
        z = np.clip(z, -self.sigma_cap, self.sigma_cap)
        return z * self._training_std + self._training_mean

    def get_current_state(self, features: pl.DataFrame | np.ndarray) -> StateObservation:
        if isinstance(features, pl.DataFrame):
            x = features.select(self.feature_cols).to_numpy()
        else:
            x = np.asarray(features, dtype=float)
        if x.ndim == 1:
            x = x.reshape(1, -1)
        x_w = self._winsorize_inference(x)
        # Posterior over hidden states for the *last* observation
        log_probs = self.hmm_model.predict_proba(x_w)
        probs = np.asarray(log_probs[-1], dtype=float)
        probs = probs / probs.sum()
        dominant = int(np.argmax(probs))
        max_prob = float(probs[dominant])
        uncertainty = 1.0 - max_prob
        transition_signal = max_prob < (1.0 - TRANSITION_UNCERTAINTY_THRESHOLD)
        return StateObservation(
            state_probs=probs,
            dominant_state_id=dominant,
            state_uncertainty=uncertainty,
            transition_signal=bool(transition_signal),
        )

    def decode_path(self, features: pl.DataFrame | np.ndarray) -> np.ndarray:
        """Viterbi-decoded state path over every row in ``features``."""
        if isinstance(features, pl.DataFrame):
            x = features.select(self.feature_cols).to_numpy()
        else:
            x = np.asarray(features, dtype=float)
        x_w = self._winsorize_inference(x)
        return np.asarray(self.hmm_model.predict(x_w))


def train_market_state_engine(
    feature_history: pl.DataFrame,
    feature_cols: list[str],
    k: int,
    audit_log: AuditLog,
    sigma_cap: float = 4.0,
    random_state: int = 42,
) -> MarketStateEngine:
    """Fit a Winsorised Gaussian HMM with ``k`` states.

    Records training to the audit log *before* fitting.
    """
    audit_log.record("layer1", "train_market_state_engine", {"k": k})

    X = feature_history.select(feature_cols).to_numpy()
    mu = np.nanmean(X, axis=0, keepdims=True)
    sd = np.nanstd(X, axis=0, ddof=1, keepdims=True)
    X_w = winsorize(X, sigma_cap)

    model = hmm.GaussianHMM(
        n_components=k,
        covariance_type="full",
        n_iter=200,
        random_state=random_state,
    )
    model.fit(X_w)

    engine = MarketStateEngine(
        hmm_model=model, feature_cols=feature_cols, sigma_cap=sigma_cap
    )
    engine.attach_training_moments(mu, sd)
    logger.info("market_state_engine_trained", k=k, n_obs=len(X_w))
    return engine
