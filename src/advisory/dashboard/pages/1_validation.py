"""Validation page — the default landing page.

Answers: "Has the system been validated?  Can I trust what I'm about to see?"
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src.advisory.dashboard.components.validation_badge import (
    badge_emoji,
    badge_label,
)
from src.advisory.dashboard.services import (
    list_layer_status_rows,
    open_main_conn,
)
from src.advisory.dashboard.state import init_session_state
from src.advisory.layer0_validation.deflated_sharpe import STATIC_TRIAL_FLOOR


st.set_page_config(page_title="Validation", layout="wide")


def render() -> None:
    init_session_state()
    st.title("Layer 0 — Validation status")
    st.caption(
        "Every other page is gated on these reports.  A row that says "
        "'no_report' means that layer has not yet been signed off."
    )

    conn = open_main_conn()
    rows = list_layer_status_rows(conn)

    df = pd.DataFrame(rows)
    df["badge"] = df["status"].map(lambda s: f"{badge_emoji(s)} {badge_label(s)}")
    show = df[
        [
            "layer",
            "badge",
            "walk_forward_sharpe",
            "cpcv_p30_sharpe",
            "deflated_sharpe",
            "survivorship_coverage",
            "rationale",
        ]
    ].rename(
        columns={
            "badge": "Status",
            "walk_forward_sharpe": "WF Sharpe",
            "cpcv_p30_sharpe": "CPCV p30",
            "deflated_sharpe": "DSR",
            "survivorship_coverage": "Survivorship",
            "rationale": "Rationale",
        }
    )

    st.dataframe(show, use_container_width=True, hide_index=True)

    st.divider()

    st.subheader("Deflated Sharpe — trial-count floor")
    st.markdown(
        f"""
        The Deflated Sharpe is computed against
        `n_trials = max(audit_count, STATIC_TRIAL_FLOOR)`, where
        `STATIC_TRIAL_FLOOR = {STATIC_TRIAL_FLOOR}`.  The audit log is the
        authoritative source for the trial count — callers cannot
        understate it.
        """
    )

    if df["survivorship_coverage"].notna().any():
        st.subheader("Survivorship coverage")
        st.write(df[["layer", "survivorship_coverage"]].dropna())


render()
