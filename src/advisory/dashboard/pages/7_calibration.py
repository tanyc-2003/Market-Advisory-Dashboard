"""Calibration page (Layer 9)."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src.advisory.dashboard.services import get_journal_polars, open_main_conn
from src.advisory.dashboard.state import init_session_state
from src.advisory.layer9_calibration.calibration import (
    ECE_MODERATE,
    ECE_WELL_CALIBRATED,
    TraderCalibrationSystem,
)


st.set_page_config(page_title="Calibration", layout="wide")


def render() -> None:
    init_session_state()
    conn = open_main_conn()
    journal = get_journal_polars(conn)

    st.title("Trader Calibration")
    cal = TraderCalibrationSystem()
    report = cal.evaluate(journal)

    if report["status"] == "INSUFFICIENT_DATA":
        st.info(
            f"Need at least {report['min_required']} completed entries; "
            f"have {report['n_entries']}."
        )
        return

    cols = st.columns(3)
    cols[0].metric("Brier score", f"{report['brier']:.4f}")
    cols[1].metric(
        "ECE",
        f"{report['ece']:.4f}",
        delta=(
            "well-calibrated"
            if report["ece"] < ECE_WELL_CALIBRATED
            else (
                "moderate" if report["ece"] < ECE_MODERATE else "poor"
            )
        ),
    )
    cols[2].metric("Calibration band", report["calibration_band"])

    rel = pd.DataFrame(report["reliability"])
    st.subheader("Reliability diagram")
    st.line_chart(rel.set_index("confidence")[["avg_predicted", "avg_observed"]])

    st.subheader("Thesis drift")
    drift = cal.detect_thesis_drift(journal)
    st.metric("Invalidated-and-lost trades", drift["n_invalidated_losses"])
    if drift["warning"]:
        st.warning(
            f"Thesis drift exceeds threshold ({drift['threshold']}). "
            "Trades held after thesis was invalidated."
        )


render()
