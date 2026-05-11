"""Layer 1 — Market State Engine (Winsorised Gaussian HMM)."""
from .dimensionality import R2_ADEQUACY_FLOOR, dimensionality_adequacy
from .engine import (
    TRANSITION_UNCERTAINTY_THRESHOLD,
    MarketStateEngine,
    train_market_state_engine,
    winsorize,
)
from .k_selector import select_k_oos
from .normalizer import (
    EWMA_CLIP,
    FEATURE_HALFLIVES,
    ewma_normalize,
    normalize_feature_matrix,
)

__all__ = [
    "EWMA_CLIP",
    "FEATURE_HALFLIVES",
    "MarketStateEngine",
    "R2_ADEQUACY_FLOOR",
    "TRANSITION_UNCERTAINTY_THRESHOLD",
    "dimensionality_adequacy",
    "ewma_normalize",
    "normalize_feature_matrix",
    "select_k_oos",
    "train_market_state_engine",
    "winsorize",
]
