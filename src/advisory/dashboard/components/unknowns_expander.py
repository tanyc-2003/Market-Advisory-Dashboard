"""Collapsed Unknowns expander — always present on every page."""
from __future__ import annotations


UNKNOWNS_EXPANDER_TITLE: str = "⚠️ What This System Does Not Know"


def render_unknowns_section(unknowns: list[str]) -> None:
    """Render the unknowns inside a default-collapsed expander."""
    import streamlit as st

    with st.expander(UNKNOWNS_EXPANDER_TITLE, expanded=False):
        if not unknowns:
            st.markdown("_(no unknowns surfaced yet — Layer 0 has not produced output)_")
            return
        for u in unknowns:
            st.markdown(f"- {u}")
