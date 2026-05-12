"""Trader journal page (Layer 8)."""
from __future__ import annotations

from datetime import date

import streamlit as st

from src.advisory.dashboard.services import (
    get_journal_polars,
    get_journal_store,
    open_main_conn,
)
from src.advisory.dashboard.state import init_session_state
from src.advisory.layer8_journal.entry import JournalEntry, JournalEntryError


st.set_page_config(page_title="Journal", layout="wide")


def render() -> None:
    init_session_state()
    conn = open_main_conn()
    store = get_journal_store(conn)

    st.title("Trader Journal")

    with st.form("new_entry"):
        st.subheader("New entry")
        cols = st.columns(2)
        entry_id = cols[0].text_input("Entry ID", value="")
        ticker = cols[1].text_input("Ticker", value="")
        cols = st.columns(2)
        entry_date = cols[0].date_input("Entry date", value=date.today())
        direction = cols[1].radio("Direction", options=["long", "short", "avoided"])
        thesis = st.text_area("Thesis")
        cols = st.columns(2)
        primary_catalyst = cols[0].text_input("Primary catalyst")
        invalidation = cols[1].text_input("Invalidation")
        cols = st.columns(2)
        horizon = cols[0].number_input("Expected horizon (days)", min_value=1, value=10)
        confidence = cols[1].slider("Confidence (1-5)", min_value=1, max_value=5, value=3)
        submitted = st.form_submit_button("Save entry")

    if submitted:
        try:
            entry = JournalEntry(
                entry_id=entry_id or f"{ticker}-{entry_date.isoformat()}",
                ticker=ticker.upper(),
                entry_date=entry_date,
                direction=direction,
                thesis=thesis,
                primary_catalyst=primary_catalyst,
                invalidation=invalidation,
                expected_horizon=int(horizon),
                confidence_self=int(confidence),
            )
            store.save(entry)
            st.success(f"Saved entry {entry.entry_id}.")
        except JournalEntryError as exc:
            st.error(str(exc))

    st.divider()
    st.subheader("Open trades")
    opens = store.get_open_trades()
    if not opens:
        st.caption("No open trades.")
    else:
        st.dataframe(
            [
                {
                    "entry_id": e.entry_id,
                    "ticker": e.ticker,
                    "direction": e.direction,
                    "entry_date": e.entry_date,
                    "confidence": e.confidence_self,
                }
                for e in opens
            ],
            use_container_width=True,
            hide_index=True,
        )

    st.divider()
    st.subheader("Close trade")
    if opens:
        sel = st.selectbox("Open entry", options=[e.entry_id for e in opens])
        exit_date = st.date_input("Exit date", value=date.today(), key="exit_date")
        pnl_pct = st.number_input("PnL %", value=0.0, format="%.4f")
        exit_reason = st.text_input("Exit reason")
        thesis_validated = st.checkbox("Thesis validated")
        if st.button("Close trade"):
            store.close_trade(
                sel,
                exit_date=exit_date,
                pnl_pct=float(pnl_pct),
                exit_reason=exit_reason,
                thesis_validated=thesis_validated,
            )
            st.success(f"Closed {sel}.")

    st.divider()
    st.subheader("Completed trades")
    df = get_journal_polars(conn)
    if df.height:
        st.dataframe(df.to_pandas(), use_container_width=True, hide_index=True)
    else:
        st.caption("No completed trades yet.")


render()
