"""V7_lite Phase 9: UNTESTABLE_LITE_MODE branch on contradictions."""
from __future__ import annotations

import numpy as np
import polars as pl

from src.advisory.layer7_hygiene.contradictions import (
    CONTRADICTION_PAIRS,
    CONTRADICTION_STATUS,
    LITE_NULL_FEATURES,
    find_validated_contradictions,
)


def _frame_with_drift(seed: int = 0) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    n = 600
    return pl.DataFrame(
        {
            "momentum_norm": rng.normal(0, 1, n),
            "breadth_pct_above_ma50_norm": rng.normal(0, 1, n),
            "earnings_revision_z": rng.normal(0, 1, n),  # value, but lite says untestable
            "hy_spread_roc_21d_norm": rng.normal(0, 1, n),
            "rsi_14_norm": rng.normal(0, 1, n),
            "prob_positive_10d": rng.normal(0, 1, n),
            "realized_vol_percentile_norm": rng.normal(0, 1, n),
            "ret_fwd_10d": rng.normal(0.001, 0.02, n),
        }
    )


def test_earnings_pair_emits_untestable_lite():
    df = _frame_with_drift()
    out = find_validated_contradictions(df, app_mode="v7_lite")
    # Pairs containing earnings_revision_z appear with UNTESTABLE_LITE status.
    untestable = [r for r in out if r.get("status") == "UNTESTABLE_LITE"]
    assert untestable
    assert any(
        "earnings_revision_z" in (r["feature_a"], r["feature_b"]) for r in untestable
    )


def test_untestable_message_text_pinned():
    df = _frame_with_drift()
    out = find_validated_contradictions(df, app_mode="v7_lite")
    for r in out:
        if r.get("status") == "UNTESTABLE_LITE":
            assert r["message"] == CONTRADICTION_STATUS["UNTESTABLE_LITE"]


def test_institutional_mode_does_not_emit_untestable():
    df = _frame_with_drift()
    out = find_validated_contradictions(df, app_mode="v7_institutional")
    assert not any(r.get("status") == "UNTESTABLE_LITE" for r in out)


def test_lite_null_features_pinned():
    assert "earnings_revision_z" in LITE_NULL_FEATURES
    assert "analyst_upgrade_z" in LITE_NULL_FEATURES


def test_lite_does_not_silently_drop_sharadar_pairs():
    df = _frame_with_drift()
    out = find_validated_contradictions(df, app_mode="v7_lite")
    # Every pair with a null feature should appear once in the output.
    null_pairs = [
        (a, b) for a, b in CONTRADICTION_PAIRS
        if a in LITE_NULL_FEATURES or b in LITE_NULL_FEATURES
    ]
    for a, b in null_pairs:
        assert any(
            r["feature_a"] == a and r["feature_b"] == b for r in out
        ), f"Pair ({a}, {b}) silently dropped in V7_lite"
