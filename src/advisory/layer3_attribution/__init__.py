"""Layer 3 — Signal Attribution (interventional SHAP)."""
from .shap_layer import (
    BACKGROUND_LOOKBACK_DAYS,
    BACKGROUND_REFRESH_DAYS,
    REDUNDANCY_DOMINANCE_THRESHOLD,
    TIGHT_MARGIN_THRESHOLD,
    ConfigurationError,
    SignalAttributionLayer,
    calibrate_model,
    detect_factor_redundancy,
)

__all__ = [
    "BACKGROUND_LOOKBACK_DAYS",
    "BACKGROUND_REFRESH_DAYS",
    "ConfigurationError",
    "REDUNDANCY_DOMINANCE_THRESHOLD",
    "SignalAttributionLayer",
    "TIGHT_MARGIN_THRESHOLD",
    "calibrate_model",
    "detect_factor_redundancy",
]
