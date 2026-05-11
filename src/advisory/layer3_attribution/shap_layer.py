"""Per-asset SHAP attribution.

Architectural decisions enforced here:

  * ``feature_perturbation="interventional"`` always.  Path-dependent
    SHAP is rejected; the constructor raises if it cannot build an
    interventional explainer.
  * Every ``explain_asset()`` call returns a ``background_vintage`` ISO
    date.  The dashboard must display it; this is not optional.
  * Background refresh cadence: ``BACKGROUND_REFRESH_DAYS=5`` calendar
    days; lookback ``BACKGROUND_LOOKBACK_DAYS=252`` days.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import numpy as np
import polars as pl
import shap
import structlog
from sklearn.calibration import CalibratedClassifierCV

logger = structlog.get_logger(__name__)


BACKGROUND_REFRESH_DAYS: int = 5
BACKGROUND_LOOKBACK_DAYS: int = 252
TIGHT_MARGIN_THRESHOLD: float = 0.50
REDUNDANCY_DOMINANCE_THRESHOLD: float = 0.50


class ConfigurationError(RuntimeError):
    """Raised on configuration that would silently violate architectural invariants."""


def calibrate_model(model: Any, X_calib: np.ndarray, y_calib: np.ndarray) -> Any:
    """Wrap ``model`` in isotonic-calibrated probability output.

    Logs ECE for the calibrated model to aid Layer 0 sign-off.
    """
    calibrated = CalibratedClassifierCV(model, method="isotonic", cv="prefit")
    calibrated.fit(X_calib, y_calib)
    probs = calibrated.predict_proba(X_calib)[:, 1]
    ece = _expected_calibration_error(probs, y_calib)
    logger.info("calibration_complete", ece=ece, n_calib=len(y_calib))
    return calibrated


def _expected_calibration_error(
    probs: np.ndarray, y: np.ndarray, n_bins: int = 10
) -> float:
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    n = len(probs)
    if n == 0:
        return 0.0
    ece = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (probs >= lo) & (probs < hi)
        if not mask.any():
            continue
        avg_p = float(probs[mask].mean())
        avg_y = float(y[mask].mean())
        ece += (mask.sum() / n) * abs(avg_p - avg_y)
    return ece


@dataclass
class SignalAttributionLayer:
    model: Any
    feature_cols: list[str]
    background_provider: Any
    """A callable ``today -> np.ndarray`` that returns the background
    matrix for the lookback window ending at ``today``."""
    today: date
    background_vintage: date = field(init=False)
    explainer: Any = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not hasattr(self.model, "predict_proba"):
            raise TypeError(
                "model must support predict_proba(). "
                "Ensure isotonic calibration has been applied."
            )
        self._build_explainer(self.today)

    def _build_explainer(self, as_of: date) -> None:
        background = self.background_provider(as_of)
        background = np.asarray(background, dtype=float)
        if background.ndim != 2 or background.shape[1] != len(self.feature_cols):
            raise ConfigurationError(
                f"background shape {background.shape} incompatible with "
                f"{len(self.feature_cols)} features"
            )
        try:
            self.explainer = shap.TreeExplainer(
                self.model,
                data=background,
                feature_perturbation="interventional",
            )
        except Exception as exc:
            raise ConfigurationError(
                "Could not construct interventional TreeExplainer. "
                "Path-dependent SHAP is forbidden; cannot fall back."
            ) from exc
        self.background_vintage = as_of
        logger.info(
            "shap_background_built",
            vintage=as_of.isoformat(),
            n_background=len(background),
        )

    def _maybe_refresh(self, as_of: date) -> None:
        if (as_of - self.background_vintage).days >= BACKGROUND_REFRESH_DAYS:
            self._build_explainer(as_of)

    def explain_asset(
        self,
        features: np.ndarray,
        ticker: str,
        as_of: date,
    ) -> dict[str, Any]:
        self._maybe_refresh(as_of)
        x = np.asarray(features, dtype=float).reshape(1, -1)
        shap_values = self.explainer.shap_values(x)
        if isinstance(shap_values, list):
            shap_values = shap_values[1] if len(shap_values) > 1 else shap_values[0]
        contributions = np.asarray(shap_values).ravel()
        order = np.argsort(-np.abs(contributions))
        top_idx = order[:3]
        top_features = [self.feature_cols[i] for i in top_idx]
        top_magnitudes = np.abs(contributions[top_idx])

        if len(top_magnitudes) >= 2 and top_magnitudes[0] > 0:
            ratio = top_magnitudes[1] / top_magnitudes[0]
        else:
            ratio = 0.0
        tight_top_margin = bool(ratio >= (1.0 - TIGHT_MARGIN_THRESHOLD))

        all_contributions = {
            self.feature_cols[i]: float(contributions[i])
            for i in range(len(self.feature_cols))
        }

        result = {
            "ticker": ticker,
            "as_of": as_of.isoformat(),
            "background_vintage": self.background_vintage.isoformat(),
            "top_features": top_features,
            "top_contributions": [float(v) for v in contributions[top_idx]],
            "tight_top_margin": tight_top_margin,
            "all_contributions": all_contributions,
        }
        return result


def detect_factor_redundancy(
    asset_attributions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Flag when too many assets share the same primary driver.

    Called at the watchlist / portfolio level.
    """
    if not asset_attributions:
        return {
            "redundancy_warning": False,
            "dominant_driver": None,
            "dominance_share": 0.0,
            "n_assets": 0,
        }

    primary_drivers = [
        a["top_features"][0]
        for a in asset_attributions
        if a.get("top_features")
    ]
    if not primary_drivers:
        return {
            "redundancy_warning": False,
            "dominant_driver": None,
            "dominance_share": 0.0,
            "n_assets": 0,
        }

    counts: dict[str, int] = {}
    for f in primary_drivers:
        counts[f] = counts.get(f, 0) + 1
    dominant, count = max(counts.items(), key=lambda kv: kv[1])
    share = count / len(primary_drivers)
    return {
        "redundancy_warning": share >= REDUNDANCY_DOMINANCE_THRESHOLD,
        "dominant_driver": dominant,
        "dominance_share": share,
        "n_assets": len(primary_drivers),
    }
