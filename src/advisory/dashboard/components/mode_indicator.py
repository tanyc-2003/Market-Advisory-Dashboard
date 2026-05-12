"""Sidebar mode indicator.

Renders on every page.  Three states:

* ``v7_lite`` — Scanner+ mode, yfinance + FRED + CBOE data.
* ``v7_institutional`` — Polygon + Sharadar configured.
* ``v7_institutional + developer mode`` — institutional mode requested
  but paid keys absent; system runs on synthetic data with a loud badge.
"""
from __future__ import annotations

from typing import Any


LITE_MODE_BLOCK: str = (
    "**Mode:** `V7_lite` (Scanner+)\n\n"
    "**Data:** yfinance · FRED · CBOE daily (free)\n\n"
    "**HMM:** `hmm_v7_lite.pkl` (9-dim)\n\n"
    "⚠️ Survivorship bias active\n\n"
    "🔴 Locked: Signal Attribution, Risk Model"
)

INSTITUTIONAL_MODE_BLOCK: str = (
    "**Mode:** `V7 Institutional`\n\n"
    "**Data:** Polygon · Sharadar · FRED · CBOE\n\n"
    "**HMM:** `hmm_v7_institutional.pkl`\n\n"
    "✅ Full validation active"
)

DEVELOPER_MODE_BLOCK: str = (
    "**Mode:** `V7 Institutional — DEVELOPER MODE`\n\n"
    "⚠️ **Synthetic data only.**\n\n"
    "Polygon and Sharadar API keys are not configured. The system is "
    "running on the deterministic synthetic universe so you can exercise "
    "the dashboard, but no real market data is being read.\n\n"
    "Set `POLYGON_API_KEY` and `SHARADAR_API_KEY` in `.env` to enable "
    "the live institutional data path, or switch to `APP_MODE=v7_lite` "
    "for free real-data sources."
)


def mode_block_for(app_mode: str, developer_mode: bool) -> str:
    """Pick the right sidebar markdown block for the active mode."""
    if app_mode == "v7_lite":
        return LITE_MODE_BLOCK
    if developer_mode:
        return DEVELOPER_MODE_BLOCK
    return INSTITUTIONAL_MODE_BLOCK


def render_sidebar_mode_indicator(
    app_mode: str,
    developer_mode: bool = False,
) -> None:
    """Render the sidebar block.  Imports Streamlit lazily."""
    import streamlit as st

    block = mode_block_for(app_mode, developer_mode)
    with st.sidebar:
        st.markdown("---")
        if developer_mode:
            st.error(block)
        elif app_mode == "v7_lite":
            st.warning(block)
        else:
            st.success(block)
        st.markdown("---")
