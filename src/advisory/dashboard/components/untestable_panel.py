"""``UNTESTABLE_LITE_MODE`` panel for the Decision Hygiene page.

Pairs that reference V7_lite-null features (e.g. ``earnings_revision_z``)
land here.  They are rendered **below** the validated contradiction
alerts so they are surfaced — not silently dropped.
"""
from __future__ import annotations

from typing import Any

from src.advisory.layer7_hygiene.contradictions import CONTRADICTION_STATUS


def render_untestable_panel(untestable_pairs: list[dict[str, Any]]) -> None:
    """Render the collapsed panel of pairs that couldn't be tested in V7_lite."""
    import streamlit as st

    if not untestable_pairs:
        return
    with st.expander(
        f"⚠️ {len(untestable_pairs)} contradiction pair(s) could not be tested "
        f"in V7_lite mode",
        expanded=False,
    ):
        st.markdown(
            "These pairs may represent real contradictions but cannot "
            "be empirically confirmed or denied without Sharadar PIT data."
        )
        for pair in untestable_pairs:
            st.markdown(
                f"- **({pair['feature_a']}, {pair['feature_b']})** — "
                f"{CONTRADICTION_STATUS['UNTESTABLE_LITE']}"
            )
