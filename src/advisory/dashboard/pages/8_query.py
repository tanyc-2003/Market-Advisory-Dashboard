"""LLM interface page (Layer 9-llm).

Hidden when :data:`config.settings.settings.llm_enabled` is False — the
page emits a message and calls :func:`streamlit.stop` so no LLM code
runs.  Set ``LLM_ENABLED=true`` in `.env` to enable.
"""
from __future__ import annotations

import streamlit as st

from config.settings import settings
from src.advisory.dashboard.state import init_session_state


st.set_page_config(page_title="Query (LLM)", layout="wide")


def render() -> None:
    init_session_state()
    st.title("LLM query (optional)")

    if not settings.llm_enabled:
        st.info(
            "The LLM interface is disabled.  Set `LLM_ENABLED=true` in your "
            "`.env` file and restart Streamlit to enable this page."
        )
        st.stop()

    # Lazy imports so the module is importable when the LLM stack is not
    # installed.
    from datetime import date

    from src.advisory.layer_llm.context import build_context_packet
    from src.advisory.layer_llm.interface import CachedLLMInterface

    query = st.text_area("Analyst query", height=120)
    if not query:
        return

    packet = build_context_packet(
        analyst_query=query,
        market_state={"summary": "(market state placeholder)"},
        analog_result={},
        attribution_map={},
        alerts=[],
        calibration={},
        unknowns=[],
    )
    with st.expander("Context packet sent to the LLM"):
        st.json(packet.__dict__)

    interface = CachedLLMInterface()
    response = interface.query(packet, as_of_date=date.today())

    cache_label = "Cached (TTL 1d)" if response.get("cache_hit") else "Live inference"
    st.caption(f"**{cache_label}**")
    if response.get("error"):
        st.error(response["response"])
    else:
        st.markdown(response["response"])


render()
