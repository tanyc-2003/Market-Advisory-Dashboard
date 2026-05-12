"""Market State Engine page (Layer 1)."""
from __future__ import annotations

import numpy as np
import streamlit as st

from config.settings import settings
from src.advisory.dashboard.components.survivorship_panel import (
    render_survivorship_panel_permanent,
)
from src.advisory.dashboard.components.unknowns_expander import (
    render_unknowns_section,
)
from src.advisory.dashboard.components.validation_badge import (
    render_blocked_output,
    render_research_preview_banner,
)
from src.advisory.dashboard.services import get_validation_report, open_main_conn
from src.advisory.dashboard.state import (
    get_last_market_state,
    init_session_state,
)
from src.advisory.layer1_market_state.engine import (
    TRANSITION_UNCERTAINTY_THRESHOLD,
)


st.set_page_config(page_title="Market State", layout="wide")


def render() -> None:
    init_session_state()
    conn = open_main_conn()
    report = get_validation_report(conn, "layer1")

    st.title("Market State Engine")

    if settings.app_mode == "v7_lite":
        render_survivorship_panel_permanent(settings.survivorship_bias_estimate())
        st.caption(
            "V7_lite Feature Dimensions (9): trend · volatility · breadth · "
            "liquidity · macro · correlation · options_proxy (VIX9D/1M/3M + "
            "SKEW + P/C ratio) · sector_relative_return_252d · fundamental "
            "(placeholder).  Missing in lite tier: PIT earnings revisions, "
            "25-delta skew surface, gamma positioning."
        )

    if report is not None:
        if report.status == "blocked":
            render_blocked_output("layer1", report.rationale)
            return
        if report.status == "research_preview":
            render_research_preview_banner("layer1", report.rationale)

    state = get_last_market_state()
    if state is None:
        st.info(
            "No market-state snapshot in session.  Run "
            "`scripts/run_validation.py` or populate "
            "`st.session_state['last_market_state']` from a backend job."
        )
        render_unknowns_section([])
        return

    probs = np.asarray(getattr(state, "state_probs", []), dtype=float)
    if probs.size:
        st.subheader("State probability vector")
        st.bar_chart(probs)
        st.metric("Dominant state", int(getattr(state, "dominant_state_id", -1)))
        st.metric("State uncertainty", f"{float(getattr(state, 'state_uncertainty', 0.0)):.2%}")
        if getattr(state, "transition_signal", False):
            st.warning(
                f"⚠️ Transition signal active: max probability fell below "
                f"{1 - TRANSITION_UNCERTAINTY_THRESHOLD:.0%}."
            )

    render_unknowns_section(getattr(state, "unknowns", []))


render()
