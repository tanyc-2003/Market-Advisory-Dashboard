"""HMM/Analog disagreement banner — fires when overlap drops below floor."""
from __future__ import annotations


DISAGREEMENT_OVERLAP_FLOOR: float = 0.70


def should_show_disagreement(overlap_pct: float) -> bool:
    return overlap_pct < DISAGREEMENT_OVERLAP_FLOOR


def render_disagreement_banner(overlap_pct: float, disagreement_note: str) -> None:
    if not should_show_disagreement(overlap_pct):
        return
    import streamlit as st

    st.error(f"🔀 HMM/Analog overlap {overlap_pct:.0%} — {disagreement_note}")
