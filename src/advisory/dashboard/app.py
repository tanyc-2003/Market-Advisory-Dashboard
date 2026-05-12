"""Streamlit entry point — navigation + sidebar only.

All page content lives in :mod:`src.advisory.dashboard.pages`.  Heavy
computation is done elsewhere; the dashboard only reads pre-computed
results.

Run with::

    streamlit run src/advisory/dashboard/app.py
"""
from __future__ import annotations

from datetime import date

import streamlit as st

from config.settings import settings
from src.advisory.dashboard.components.mode_indicator import (
    render_sidebar_mode_indicator,
)
from src.advisory.dashboard.components.validation_badge import (
    badge_emoji,
    badge_label,
)
from src.advisory.dashboard.services import (
    is_data_stale,
    list_layer_status_rows,
    open_main_conn,
)
from src.advisory.dashboard.state import init_session_state


st.set_page_config(
    page_title="Advisory Market Intelligence Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource
def _conn():
    return open_main_conn()


def _render_sidebar() -> None:
    conn = _conn()
    with st.sidebar:
        st.title("System Health")

        rows = list_layer_status_rows(conn)
        for r in rows:
            # Layers 3 & 4 are LOCKED in V7_lite — flag them in the sidebar.
            if settings.app_mode == "v7_lite" and r["layer"] in ("layer3", "layer4"):
                st.markdown(f"🔴  **{r['layer']}** — Locked (V7_lite)")
                continue
            st.markdown(
                f"{badge_emoji(r['status'])}  **{r['layer']}** — {badge_label(r['status'])}"
            )

        st.divider()
        as_of = st.session_state.get("as_of_date") or date.today()
        st.caption(f"Data as of: **{as_of.isoformat()}**")
        if is_data_stale(as_of, date.today()):
            st.warning("Data is more than 2 trading days old.")

        if settings.llm_enabled:
            st.success("LLM interface enabled (Page 8 visible).")
        else:
            st.info("LLM interface disabled (Page 8 hidden).")

    # Mode indicator block: lite warning, institutional success, or
    # bright red developer-mode error when paid keys are missing.
    render_sidebar_mode_indicator(
        app_mode=settings.app_mode,
        developer_mode=settings.developer_mode,
    )


def main() -> None:
    init_session_state()
    _render_sidebar()

    st.title("Advisory Market Intelligence Dashboard")

    if settings.app_mode == "v7_lite":
        st.warning(
            "Running in **V7_lite (Scanner+)** mode — free data sources, "
            "Layer 3 (Signal Attribution) and Layer 4 (Risk Model) locked, "
            "survivorship bias disclosed on every analog distribution."
        )
    elif settings.developer_mode:
        st.error(
            "Running in **V7 Institutional — Developer Mode**.  Polygon and "
            "Sharadar keys are not configured, so the system is reading "
            "synthetic data only.  Configure paid API keys in `.env` to "
            "switch to the live institutional path, or set "
            "`APP_MODE=v7_lite` for free real-data sources."
        )
    else:
        st.success(
            "Running in **V7 Institutional** mode with live paid data.  "
            "All layers active."
        )

    st.write(
        "Open the **Validation** page first — every other page is gated "
        "on the Layer 0 sign-off shown there."
    )
    st.write("Pages are listed in the left navigation.")


if __name__ == "__main__":
    main()
