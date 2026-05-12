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

__all__ = [
    "ES_QUANTILE",
    "KELLY_ABSOLUTE_CAP",
    "KELLY_LOW_SAMPLE_THRESHOLD",
    "SIZING_NOTE",
    "sizing_diagnostics",
]
