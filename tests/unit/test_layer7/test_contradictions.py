"""Tests for find_validated_contradictions (Phase 8)."""
from __future__ import annotations

import numpy as np
import polars as pl

from src.advisory.layer7_hygiene.contradictions import (
    CONTRADICTION_LABEL,
    CONTRADICTION_PAIRS,
    find_validated_contradictions,
)


def _frame_with_contradiction(seed: int = 0) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    n = 800
    a = rng.normal(0, 1, n)
    b = rng.normal(0, 1, n)
    # When BOTH a and b are high, force NEGATIVE forward returns; when
    # both are low, force POSITIVE — a strong, easily-detected contradiction.
    fwd = rng.normal(0, 0.01, n)
    joint_hi = (a > np.median(a)) & (b > np.median(b))
    joint_lo = (a < np.median(a)) & (b < np.median(b))
    fwd[joint_hi] -= 0.05
    fwd[joint_lo] += 0.05
    return pl.DataFrame(
        {
            "momentum_norm": a,
            "breadth_pct_above_ma50_norm": b,
            "ret_fwd_10d": fwd,
        }
    )


def test_fisher_test_surfaces_real_contradiction():
    df = _frame_with_contradiction()
    result = find_validated_contradictions(df)
    assert len(result) >= 1


def test_label_contains_exact_string():
    df = _frame_with_contradiction()
    result = find_validated_contradictions(df)
    for r in result:
        assert r["label"] == CONTRADICTION_LABEL


def test_result_length_at_most_pair_count():
    df = _frame_with_contradiction()
    result = find_validated_contradictions(df)
    assert len(result) <= len(CONTRADICTION_PAIRS)


def test_missing_columns_skipped():
    df = pl.DataFrame(
        {"ret_fwd_10d": np.zeros(50), "momentum_norm": np.zeros(50)}
    )
    result = find_validated_contradictions(df)
    assert result == []


def test_high_significance_filters_real_contradictions_out():
    df = _frame_with_contradiction()
    # Insist on p < 1e-200 — nothing should survive.
    result = find_validated_contradictions(df, significance=1e-200)
    assert result == []
