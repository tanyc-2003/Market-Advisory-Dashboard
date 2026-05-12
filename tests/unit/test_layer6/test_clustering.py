"""Tests for detect_correlation_clusters (Phase 6)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.advisory.layer6_portfolio.clustering import (
    CLUSTER_WARNING_TEXT,
    detect_correlation_clusters,
)


def _highly_correlated_returns(seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = 250
    z = rng.normal(0, 0.01, n)
    return pd.DataFrame(
        {
            "A": z + rng.normal(0, 0.001, n),
            "B": z + rng.normal(0, 0.001, n),
            "C": rng.normal(0, 0.01, n),
            "D": rng.normal(0, 0.01, n),
        }
    )


def test_highly_correlated_pair_identified():
    rets = _highly_correlated_returns()
    weights = {"A": 0.25, "B": 0.25, "C": 0.25, "D": 0.25}
    clusters = detect_correlation_clusters(rets, weights)
    assert any({"A", "B"}.issubset(set(c["members"])) for c in clusters)


def test_uncorrelated_pair_excluded():
    rets = _highly_correlated_returns()
    weights = {"A": 0.25, "B": 0.25, "C": 0.25, "D": 0.25}
    clusters = detect_correlation_clusters(rets, weights)
    for c in clusters:
        assert not {"C", "D"}.issubset(set(c["members"]))


def test_warning_text_matches_architecture():
    rets = _highly_correlated_returns()
    clusters = detect_correlation_clusters(
        rets, {"A": 0.5, "B": 0.5}
    )
    for c in clusters:
        assert c["warning"] == CLUSTER_WARNING_TEXT


def test_combined_weight_summed_correctly():
    rets = _highly_correlated_returns()
    clusters = detect_correlation_clusters(
        rets, {"A": 0.3, "B": 0.2, "C": 0.5}
    )
    for c in clusters:
        if {"A", "B"}.issubset(set(c["members"])):
            assert abs(c["combined_weight"] - 0.5) < 1e-9


def test_short_history_returns_empty():
    rets = _highly_correlated_returns().head(10)
    clusters = detect_correlation_clusters(rets, {"A": 0.5, "B": 0.5})
    assert clusters == []
