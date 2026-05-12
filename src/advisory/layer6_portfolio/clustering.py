"""Correlation cluster detection for the portfolio."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import structlog

logger = structlog.get_logger(__name__)


CLUSTER_CORRELATION_THRESHOLD: float = 0.75
CLUSTER_WARNING_TEXT: str = "These positions behave as a single trade."
MIN_HISTORY_DAYS: int = 30


def detect_correlation_clusters(
    returns: pd.DataFrame,
    weights: dict[str, float],
    threshold: float = CLUSTER_CORRELATION_THRESHOLD,
    min_cluster_size: int = 2,
) -> list[dict[str, Any]]:
    """Group tickers whose pairwise correlation exceeds ``threshold``.

    Returns a list of dicts, one per cluster, each containing the
    members, their summed portfolio weight, and the architecture-pinned
    warning text.
    """
    if returns.shape[0] < MIN_HISTORY_DAYS:
        logger.warning(
            "clustering_insufficient_history", n_rows=int(returns.shape[0])
        )
        return []

    held = [t for t, w in weights.items() if abs(w) > 1e-12 and t in returns.columns]
    if len(held) < min_cluster_size:
        return []

    sub = returns[held].dropna(how="all")
    corr = sub.corr().to_numpy()

    n = len(held)
    visited: set[int] = set()
    clusters: list[set[int]] = []
    for i in range(n):
        if i in visited:
            continue
        # BFS over the (correlation >= threshold) graph
        queue = [i]
        component: set[int] = set()
        while queue:
            j = queue.pop()
            if j in component:
                continue
            component.add(j)
            for k in range(n):
                if k == j or k in component:
                    continue
                if abs(corr[j, k]) >= threshold:
                    queue.append(k)
        visited |= component
        if len(component) >= min_cluster_size:
            clusters.append(component)

    out: list[dict[str, Any]] = []
    for component in clusters:
        members = sorted(held[i] for i in component)
        combined_weight = float(sum(weights.get(m, 0.0) for m in members))
        out.append(
            {
                "members": members,
                "combined_weight": combined_weight,
                "n_members": len(members),
                "warning": CLUSTER_WARNING_TEXT,
            }
        )
    return out
