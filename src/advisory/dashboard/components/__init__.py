"""Reusable Streamlit components.

Each component carries the *exact* architecture text verbatim — these
strings are part of the contract with the trader and must not be
paraphrased.
"""
from .disagreement_banner import (
    DISAGREEMENT_OVERLAP_FLOOR,
    render_disagreement_banner,
)
from .distribution_chart import render_analog_return_distribution
from .unknowns_expander import (
    UNKNOWNS_EXPANDER_TITLE,
    render_unknowns_section,
)
from .validation_badge import (
    BLOCKED_MESSAGE_TEMPLATE,
    RESEARCH_PREVIEW_HEADLINE,
    badge_emoji,
    badge_label,
    render_blocked_output,
    render_research_preview_banner,
    render_validation_badge,
)

__all__ = [
    "BLOCKED_MESSAGE_TEMPLATE",
    "DISAGREEMENT_OVERLAP_FLOOR",
    "RESEARCH_PREVIEW_HEADLINE",
    "UNKNOWNS_EXPANDER_TITLE",
    "badge_emoji",
    "badge_label",
    "render_analog_return_distribution",
    "render_blocked_output",
    "render_disagreement_banner",
    "render_research_preview_banner",
    "render_unknowns_section",
    "render_validation_badge",
]
