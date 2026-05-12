"""Layer 10 — Position Sizing Diagnostics.

These are *diagnostic computations*, not recommendations. Outputs are
always capped at :data:`KELLY_ABSOLUTE_CAP`, are tail-aware (loss term =
``|ES_5|``), and are haircut by regime uncertainty + HMM/Analog
disagreement.
"""
from .diagnostics import (
    ES_QUANTILE,
    KELLY_ABSOLUTE_CAP,
    KELLY_LOW_SAMPLE_THRESHOLD,
    SIZING_NOTE,
    sizing_diagnostics,
)
from .lite_diagnostics import inject_synthetic_wipeouts, sizing_diagnostics_lite

__all__ = [
    "ES_QUANTILE",
    "KELLY_ABSOLUTE_CAP",
    "KELLY_LOW_SAMPLE_THRESHOLD",
    "SIZING_NOTE",
    "inject_synthetic_wipeouts",
    "sizing_diagnostics",
    "sizing_diagnostics_lite",
]
