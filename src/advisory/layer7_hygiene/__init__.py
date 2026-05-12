"""Layer 7 — Decision Hygiene.

Surfaces *evidence about evidence*: validated contradictions between
features, FDR-corrected alert filtering, calibrated confidence
language, and an always-on Unknowns section.
"""
from .confidence import CONFIDENCE_LANGUAGE, get_confidence_language
from .contradictions import (
    CONTRADICTION_LABEL,
    CONTRADICTION_PAIRS,
    CONTRADICTION_STATUS,
    LITE_NULL_FEATURES,
    find_validated_contradictions,
)
from .fdr import (
    SEVERITY_SCORES,
    apply_fdr_correction,
    filter_top_k_alerts,
)
from .unknowns import (
    STRUCTURAL_CHANGE_UNKNOWN,
    generate_unknowns_section,
)

__all__ = [
    "CONFIDENCE_LANGUAGE",
    "CONTRADICTION_LABEL",
    "CONTRADICTION_PAIRS",
    "CONTRADICTION_STATUS",
    "LITE_NULL_FEATURES",
    "SEVERITY_SCORES",
    "STRUCTURAL_CHANGE_UNKNOWN",
    "apply_fdr_correction",
    "filter_top_k_alerts",
    "find_validated_contradictions",
    "generate_unknowns_section",
    "get_confidence_language",
]
