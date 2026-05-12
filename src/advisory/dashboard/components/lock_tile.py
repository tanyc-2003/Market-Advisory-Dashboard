"""Locked-layer tile.

Replaces the body of pages whose layer returns ``{"status": "LOCKED"}``
when ``APP_MODE == "v7_lite"``.  Architecture §9 / §10 require this be
visible — locked pages must not silently disappear from navigation.
"""
from __future__ import annotations


LAYER_LOCK_REASONS: dict[str, str] = {
    "layer3": (
        "Point-in-Time fundamental data (Sharadar) is required for the "
        "SHAP attribution layer to produce interpretable per-asset "
        "contributions."
    ),
    "layer4": (
        "Point-in-Time fundamental factor returns (Sharadar) are required "
        "to compute orthogonalised factor exposures and tail betas."
    ),
}


LAYER_LOCK_TITLES: dict[str, str] = {
    "layer3": "Signal Attribution (Layer 3)",
    "layer4": "Hybrid Risk Model (Layer 4)",
}


def render_layer_lock_tile(layer_name: str) -> None:
    """Render the locked-tile section for a given layer."""
    import streamlit as st

    title = LAYER_LOCK_TITLES.get(layer_name, layer_name)
    reason = LAYER_LOCK_REASONS.get(layer_name, "Locked in V7_lite mode.")
    st.error(
        f"🔴 **{title} is locked in V7_lite mode.**\n\n"
        f"{reason}\n\n"
        f"Upgrade to V7 Institutional (set `APP_MODE=v7_institutional` "
        "in `.env` and provide Polygon + Sharadar keys) to activate."
    )
