"""Position sizing diagnostics page (Layer 10)."""
from __future__ import annotations

import numpy as np
import streamlit as st

from src.advisory.dashboard.components.unknowns_expander import (
    render_unknowns_section,
)
from src.advisory.dashboard.components.validation_badge import (
    render_blocked_output,
    render_research_preview_banner,
)
from src.advisory.dashboard.services import get_validation_report, open_main_conn
from src.advisory.dashboard.state import (
    get_last_analog_result,
    get_last_market_state,
    init_session_state,
)
from src.advisory.layer10_sizing.diagnostics import (
    KELLY_ABSOLUTE_CAP,
    KELLY_LOW_SAMPLE_THRESHOLD,
    SIZING_NOTE,
    sizing_diagnostics,
)


st.set_page_config(page_title="Sizing", layout="wide")


def render() -> None:
    init_session_state()
    conn = open_main_conn()
    report = get_validation_report(conn, "layer10_sizing")

    st.title("Position Sizing Diagnostics")
    st.metric("Absolute Kelly cap", f"{KELLY_ABSOLUTE_CAP:.0%}")
    st.caption(SIZING_NOTE)

    if report is not None:
        if report.status == "blocked":
            render_blocked_output("layer10_sizing", report.rationale)
            return
        if report.status == "research_preview":
            render_research_preview_banner("layer10_sizing", report.rationale)

    analog = get_last_analog_result()
    state = get_last_market_state()
    if analog is None or state is None:
        st.info(
            "Need both a market-state snapshot and an analog result in "
            "session.  Run an upstream pass first."
        )
        render_unknowns_section([])
        return

    global_set = getattr(analog, "global_set", analog)
    returns = np.asarray(getattr(global_set, "forward_returns", []), dtype=float)
    state_uncertainty = float(getattr(state, "state_uncertainty", 0.0))
    overlap = float(getattr(analog, "overlap_pct", 1.0))

    result = sizing_diagnostics(
        analog_returns=returns,
        state_uncertainty=state_uncertainty,
        hmm_analog_overlap_pct=overlap,
    )

    if result.get("status") == "INSUFFICIENT_ANALOGS":
        st.error(
            f"Insufficient analogs: {result['n']} < {result['min_required']} required."
        )
        return

    cols = st.columns(4)
    cols[0].metric("Raw Kelly", f"{result['raw_kelly']:.2%}")
    cols[1].metric("Haircut (standard)", f"{result['haircut_kelly_standard']:.2%}")
    cols[2].metric("Haircut (regime)", f"{result['haircut_kelly_regime']:.2%}")
    cols[3].metric("Displayed Kelly", f"{result['displayed_kelly']:.2%}")

    if result["n"] < KELLY_LOW_SAMPLE_THRESHOLD:
        st.warning(
            f"Sample fragile: {result['n']} analogs is below "
            f"{KELLY_LOW_SAMPLE_THRESHOLD}.  Treat magnitudes with scepticism."
        )

    with st.expander("Inputs to Kelly"):
        st.json(
            {
                "win_rate": result["win_rate"],
                "avg_win": result["avg_win"],
                "avg_loss": result["avg_loss"],
                "es_5": result["es_5"],
                "state_uncertainty": result["state_uncertainty"],
                "hmm_analog_overlap_pct": result["hmm_analog_overlap_pct"],
                "effective_haircut": result["effective_haircut"],
            }
        )

    render_unknowns_section(result.get("warnings", []))


render()
