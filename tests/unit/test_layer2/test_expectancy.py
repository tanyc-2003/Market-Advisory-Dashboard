"""Tests for build_conditional_expectancy_table (Phase 3)."""
from __future__ import annotations

from src.advisory.layer2_analogs.expectancy import (
    build_conditional_expectancy_table,
)


def test_returns_dataframe_with_expected_columns(synthetic_feature_history):
    table = build_conditional_expectancy_table(synthetic_feature_history)
    expected_cols = {"condition", "n_obs", "mean_fwd_return", "median_fwd_return", "hit_rate"}
    assert expected_cols.issubset(set(table.columns))


def test_small_conditions_excluded(synthetic_feature_history):
    short = synthetic_feature_history.head(5)
    table = build_conditional_expectancy_table(short)
    # Every condition has < MIN_OBS_PER_CONDITION rows after filtering
    assert table.height == 0
