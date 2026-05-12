"""Layer 4 — Hybrid Risk Model.

Combines a fundamental factor block (lagged factor returns, three
regression flavours) with a residual-factor PCA anomaly detector.
"""
from .factors import (
    FACTOR_ORDER,
    MACRO_FACTOR_PROXIES,
    orthogonalize_factors,
)
from .fundamental import (
    EW_LAMBDA_MEDIUM,
    EW_LAMBDA_SHORT,
    MIN_N_OBS,
    AssetExposureResult,
    FundamentalRiskModel,
)
from .residual_pca import (
    BOOTSTRAP_N,
    JACCARD_MATCH_THRESHOLD,
    STABILITY_THRESHOLD,
    ResidualFactorAnomalyDetector,
)

__all__ = [
    "AssetExposureResult",
    "BOOTSTRAP_N",
    "EW_LAMBDA_MEDIUM",
    "EW_LAMBDA_SHORT",
    "FACTOR_ORDER",
    "FundamentalRiskModel",
    "JACCARD_MATCH_THRESHOLD",
    "MACRO_FACTOR_PROXIES",
    "MIN_N_OBS",
    "ResidualFactorAnomalyDetector",
    "STABILITY_THRESHOLD",
    "orthogonalize_factors",
]
