"""Watchlist + attribution page (Layers 2, 3, 7)."""
from __future__ import annotations

import streamlit as st

from src.advisory.dashboard.components.disagreement_banner import (
    render_disagreement_banner,
)
from src.advisory.dashboard.components.distribution_chart import (
    render_analog_return_distribution,
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
    get_last_analog_result,
    get_selected_ticker,
    init_session_state,
    set_selected_ticker,
)


st.set_page_config(page_title="Watchlist", layout="wide")


def render() -> None:
    init_session_state()
    conn = open_main_conn()
    report = get_validation_report(conn, "layer2")

    st.title("Watchlist & Attribution")

    if report is not None:
        if report.status == "blocked":
            render_blocked_output("layer2", report.rationale)
            return
        if report.status == "research_preview":
            render_research_preview_banner("layer2", report.rationale)

    ticker = st.text_input(
        "Ticker", value=get_selected_ticker() or "", placeholder="e.g. AAPL"
    )
    if ticker:
        set_selected_ticker(ticker.upper())

    analog = get_last_analog_result()
    if analog is None:
        st.info(
            "No analog result in session.  Run an analog search to "
            "populate `st.session_state['last_analog_result']`."
        )
        render_unknowns_section([])
        return

    global_set = getattr(analog, "global_set", None)
    within_set = getattr(analog, "within_state_set", None)
    if global_set is not None:
        render_analog_return_distribution(
            global_returns=global_set.forward_returns,
            within_state_returns=(
                within_set.forward_returns if within_set is not None else None
            ),
            label=ticker or "selected ticker",
            n_global=len(global_set.indices),
            n_within_state=len(within_set.indices) if within_set is not None else None,
        )

    overlap = float(getattr(analog, "overlap_pct", 1.0))
    note = getattr(analog, "note", "") or ""
    if note:
        render_disagreement_banner(overlap, note)

    render_unknowns_section(getattr(analog, "unknowns", []))


render()
