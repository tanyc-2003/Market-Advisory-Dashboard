"""Portfolio diagnostics page (Layer 6)."""
from __future__ import annotations

import pandas as pd
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
    get_portfolio_weights,
    init_session_state,
    set_portfolio_weights,
)
from src.advisory.layer6_portfolio.clustering import CLUSTER_WARNING_TEXT
from src.advisory.layer6_portfolio.covariance import STRESS_NOTE, list_scenarios


st.set_page_config(page_title="Portfolio", layout="wide")


def render() -> None:
    init_session_state()
    conn = open_main_conn()
    report = get_validation_report(conn, "layer6")

    st.title("Portfolio Diagnostics")

    if report is not None:
        if report.status == "blocked":
            render_blocked_output("layer6", report.rationale)
            return
        if report.status == "research_preview":
            render_research_preview_banner("layer6", report.rationale)

    weights = get_portfolio_weights()
    df = pd.DataFrame(
        [{"ticker": t, "weight": w} for t, w in weights.items()]
        or [{"ticker": "", "weight": 0.0}]
    )
    edited = st.data_editor(df, num_rows="dynamic", key="portfolio_editor")
    if st.button("Save weights"):
        new = {
            row["ticker"]: float(row["weight"])
            for _, row in edited.iterrows()
            if row["ticker"]
        }
        set_portfolio_weights(new)
        st.success("Weights saved.")

    total = sum(get_portfolio_weights().values())
    if abs(total - 1.0) > 1e-6 and total > 0:
        st.warning(f"Weights sum to {total:.4f} (≠ 1.0).")

    st.divider()
    st.subheader("Stress scenarios")
    st.selectbox("Scenario", options=list_scenarios())
    st.caption(STRESS_NOTE)

    st.divider()
    st.subheader("Correlation clusters")
    st.caption(CLUSTER_WARNING_TEXT)

    render_unknowns_section([])


render()
