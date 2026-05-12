"""Layer-status badge + banners.

Three statuses come from :meth:`ValidationReport.status`:

* ``production`` — green pill
* ``research_preview`` — yellow pill + banner
* ``blocked`` — red message; the layer's output is hidden entirely

The banner / blocked-message text is part of the architectural contract.
The pure-text helpers below are unit-tested without Streamlit running.
"""
from __future__ import annotations

from typing import Any


RESEARCH_PREVIEW_HEADLINE: str = (
    "Research preview — not validated for live decision support."
)

BLOCKED_MESSAGE_TEMPLATE: str = (
    "Output hidden: {layer} did not pass validation. Rationale: {rationale}"
)


_BADGE_LABELS: dict[str, str] = {
    "production": "Production",
    "research_preview": "Research preview",
    "blocked": "Blocked",
    "no_report": "No report",
}

_BADGE_EMOJIS: dict[str, str] = {
    "production": "🟢",
    "research_preview": "🟡",
    "blocked": "🔴",
    "no_report": "⚪",
}


def badge_label(status: str) -> str:
    return _BADGE_LABELS.get(status, status)


def badge_emoji(status: str) -> str:
    return _BADGE_EMOJIS.get(status, "⚪")


def render_validation_badge(report: Any) -> None:
    """Render the status pill for a layer.

    Imports Streamlit lazily so this module is importable in tests
    without a Streamlit runtime.
    """
    import streamlit as st

    status = getattr(report, "status", "no_report")
    layer = getattr(report, "layer_name", "unknown")
    rationale = getattr(report, "rationale", "") or "n/a"
    emoji = badge_emoji(status)
    label = badge_label(status)
    st.markdown(
        f"**{emoji} {label}** — {layer}",
        help=rationale,
    )


def render_research_preview_banner(layer_name: str, rationale: str) -> None:
    import streamlit as st

    st.warning(
        f"⚠️ **{RESEARCH_PREVIEW_HEADLINE}**\n\n"
        f"Layer: `{layer_name}`\n\n"
        f"Rationale: {rationale}"
    )


def render_blocked_output(layer_name: str, rationale: str) -> None:
    import streamlit as st

    st.error(
        "🚫 "
        + BLOCKED_MESSAGE_TEMPLATE.format(layer=layer_name, rationale=rationale)
    )
