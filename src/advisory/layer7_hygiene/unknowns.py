"""Generate the always-visible Unknowns section.

The structural-change unknown is unconditional — it is always appended
last so the trader sees it on every render.
"""
from __future__ import annotations

from typing import Any


STRUCTURAL_CHANGE_UNKNOWN: str = (
    "Structural change cannot be ruled out: historical analogs do not "
    "speak to regimes that have never occurred. Treat distributional "
    "estimates as conditional on the past resembling the present."
)


def generate_unknowns_section(
    *,
    analog_result: Any | None,
    n_analogs: int,
    dimensionality_passed: bool,
    survivorship_passed: bool,
    extra_unknowns: list[str] | None = None,
) -> list[str]:
    """Return a list of human-readable unknowns.

    The final entry is always :data:`STRUCTURAL_CHANGE_UNKNOWN`.
    """
    unknowns: list[str] = []
    if extra_unknowns:
        unknowns.extend(extra_unknowns)

    if n_analogs < 15:
        unknowns.append(
            f"Only {n_analogs} historical analogs available — "
            "estimates have wide error bars."
        )
    if analog_result is not None and getattr(analog_result, "covariance_method", None) == "ledoit_wolf":
        unknowns.append(
            "Covariance was estimated by Ledoit-Wolf shrinkage (MCD fell "
            "back due to small sample) — outlier-resistance is reduced."
        )
    if not dimensionality_passed:
        unknowns.append(
            "Feature-set dimensionality adequacy is below floor — model may "
            "not span the variance space it appears to."
        )
    if not survivorship_passed:
        unknowns.append(
            "Survivorship audit did not pass for the active universe; "
            "downstream outputs should be treated as research-preview only."
        )

    unknowns.append(STRUCTURAL_CHANGE_UNKNOWN)
    return unknowns
