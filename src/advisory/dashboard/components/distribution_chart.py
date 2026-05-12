"""Plotly histogram of analog return distributions (global vs within-state)."""
from __future__ import annotations

import numpy as np


PERCENTILES = (5, 25, 50)


def build_distribution_figure(
    global_returns: np.ndarray,
    within_state_returns: np.ndarray | None,
    label: str,
    n_global: int,
    n_within_state: int | None,
) -> object:
    """Return a Plotly Figure showing the analog return distribution.

    The figure is constructed without Streamlit so it is unit-testable.
    """
    import plotly.graph_objects as go

    fig = go.Figure()
    g = np.asarray(global_returns, dtype=float)
    fig.add_trace(
        go.Histogram(
            x=g,
            name=f"Global (n={n_global}, eff. N below)",
            nbinsx=30,
            opacity=0.65,
        )
    )
    if within_state_returns is not None and len(within_state_returns):
        w = np.asarray(within_state_returns, dtype=float)
        fig.add_trace(
            go.Histogram(
                x=w,
                name=f"Within-state (n={n_within_state})",
                nbinsx=30,
                opacity=0.65,
            )
        )

    fig.update_layout(barmode="overlay")
    fig.update_layout(
        title=f"Analog 10-day forward returns — {label}",
        xaxis_title="10-day forward return",
        yaxis_title="Frequency",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    for pct in PERCENTILES:
        if g.size:
            val = float(np.percentile(g, pct))
            fig.add_vline(
                x=val,
                line_dash="dot",
                annotation_text=f"p{pct}",
                annotation_position="top",
            )
    return fig


def render_analog_return_distribution(
    global_returns: np.ndarray,
    within_state_returns: np.ndarray | None,
    label: str,
    n_global: int,
    n_within_state: int | None,
) -> None:
    """Streamlit-side wrapper."""
    import streamlit as st

    fig = build_distribution_figure(
        global_returns=global_returns,
        within_state_returns=within_state_returns,
        label=label,
        n_global=n_global,
        n_within_state=n_within_state,
    )
    st.plotly_chart(fig, use_container_width=True)
