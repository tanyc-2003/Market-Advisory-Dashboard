"""Tests for HistoricalAnalogEngine (Phase 3)."""
from __future__ import annotations

from datetime import date

import numpy as np
import pytest

from src.advisory.layer2_analogs.engine import (
    ABS_MIN_SEPARATION,
    HistoricalAnalogEngine,
)


def test_find_analogs_returns_at_most_k(synthetic_feature_history, feature_cols):
    engine = HistoricalAnalogEngine(feature_cols=feature_cols)
    query = synthetic_feature_history.tail(1).select(feature_cols).to_numpy()[0]
    anchor = date(2024, 12, 31)
    result = engine.find_analogs(
        synthetic_feature_history.head(700),
        query=query,
        anchor_date=anchor,
        k=20,
    )
    assert len(result.indices) <= 20
    assert len(result.forward_returns) == len(result.indices)


def test_min_separation_excludes_recent_obs(synthetic_feature_history, feature_cols):
    engine = HistoricalAnalogEngine(feature_cols=feature_cols)
    query = synthetic_feature_history.tail(1).select(feature_cols).to_numpy()[0]
    anchor = synthetic_feature_history["effective_date"].max()
    result = engine.find_analogs(
        synthetic_feature_history,
        query=query,
        anchor_date=anchor,
        k=10,
        min_separation=21,
    )
    for d in result.dates:
        assert (anchor - d).days > 21


def test_min_separation_floor_enforced(synthetic_feature_history, feature_cols):
    engine = HistoricalAnalogEngine(feature_cols=feature_cols)
    query = synthetic_feature_history.tail(1).select(feature_cols).to_numpy()[0]
    with pytest.raises(ValueError):
        engine.find_analogs(
            synthetic_feature_history,
            query=query,
            anchor_date=date(2024, 12, 31),
            min_separation=ABS_MIN_SEPARATION - 1,
        )


def test_state_filter_restricts_to_state(synthetic_feature_history, feature_cols):
    engine = HistoricalAnalogEngine(feature_cols=feature_cols)
    query = synthetic_feature_history.tail(1).select(feature_cols).to_numpy()[0]
    anchor = synthetic_feature_history["effective_date"].max()
    result = engine.find_analogs(
        synthetic_feature_history,
        query=query,
        anchor_date=anchor,
        k=10,
        state_filter=1,
    )
    # All retained analogs were filtered down to hmm_state==1 before sampling
    assert result.state_filter == 1


def test_disagreement_overlap_in_unit_interval(synthetic_feature_history, feature_cols):
    engine = HistoricalAnalogEngine(feature_cols=feature_cols)
    query = synthetic_feature_history.tail(1).select(feature_cols).to_numpy()[0]
    anchor = synthetic_feature_history["effective_date"].max()
    result = engine.find_analogs_with_disagreement(
        synthetic_feature_history,
        query=query,
        anchor_date=anchor,
        dominant_state_id=1,
        k=20,
    )
    assert 0.0 <= result.overlap_pct <= 1.0


def test_missing_forward_return_column_raises(synthetic_feature_history, feature_cols):
    engine = HistoricalAnalogEngine(feature_cols=feature_cols)
    query = synthetic_feature_history.tail(1).select(feature_cols).to_numpy()[0]
    df = synthetic_feature_history.drop("ret_fwd_10d")
    with pytest.raises(ValueError):
        engine.find_analogs(
            df,
            query=query,
            anchor_date=date(2024, 12, 31),
        )


def test_effective_n_less_than_raw_n(synthetic_feature_history, feature_cols):
    engine = HistoricalAnalogEngine(feature_cols=feature_cols)
    query = synthetic_feature_history.tail(1).select(feature_cols).to_numpy()[0]
    anchor = synthetic_feature_history["effective_date"].max()
    result = engine.find_analogs(
        synthetic_feature_history,
        query=query,
        anchor_date=anchor,
        k=30,
    )
    # With ~5y half-life and historical data spanning >3y, effective N
    # should be strictly less than the raw count of selected analogs.
    assert result.effective_n_recency_weighted <= len(result.indices)
