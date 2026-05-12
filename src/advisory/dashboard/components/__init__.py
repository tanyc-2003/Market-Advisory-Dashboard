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
from .lock_tile import (
    LAYER_LOCK_REASONS,
    LAYER_LOCK_TITLES,
    render_layer_lock_tile,
)
from .mode_indicator import (
    DEVELOPER_MODE_BLOCK,
    INSTITUTIONAL_MODE_BLOCK,
    LITE_MODE_BLOCK,
    mode_block_for,
    render_sidebar_mode_indicator,
)
from .survivorship_panel import (
    SURVIVORSHIP_HEADLINE,
    render_survivorship_panel_permanent,
)
from .unknowns_expander import (
    UNKNOWNS_EXPANDER_TITLE,
    render_unknowns_section,
)
from .untestable_panel import render_untestable_panel
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
    "DEVELOPER_MODE_BLOCK",
    "DISAGREEMENT_OVERLAP_FLOOR",
    "INSTITUTIONAL_MODE_BLOCK",
    "LAYER_LOCK_REASONS",
    "LAYER_LOCK_TITLES",
    "LITE_MODE_BLOCK",
    "RESEARCH_PREVIEW_HEADLINE",
    "SURVIVORSHIP_HEADLINE",
    "UNKNOWNS_EXPANDER_TITLE",
    "badge_emoji",
    "badge_label",
    "mode_block_for",
    "render_analog_return_distribution",
    "render_blocked_output",
    "render_disagreement_banner",
    "render_layer_lock_tile",
    "render_research_preview_banner",
    "render_sidebar_mode_indicator",
    "render_survivorship_panel_permanent",
    "render_unknowns_section",
    "render_untestable_panel",
    "render_validation_badge",
]
