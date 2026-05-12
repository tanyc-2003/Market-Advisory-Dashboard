"""V7_lite Phase 7: Layer 2 feature_quality_note disclosure."""
from __future__ import annotations

from datetime import date

import numpy as np

from src.advisory.layer2_analogs.engine import (
    LITE_MISSING_FEATURES,
    HistoricalAnalogEngine,
)


def test_feature_quality_note_present_in_lite_mode(
    synthetic_feature_history, feature_cols
):
    engine = HistoricalAnalogEngine(feature_cols=feature_cols, app_mode="v7_lite")
    query = synthetic_feature_history.tail(1).select(feature_cols).to_numpy()[0]
    anchor = synthetic_feature_history["effective_date"].max()
    result = engine.find_analogs_with_disagreement(
        synthetic_feature_history,
        query=query,
        anchor_date=anchor,
        dominant_state_id=1,
        k=20,
    )
    assert result.feature_quality_note is not None
    assert "earnings_revision_z" in result.feature_quality_note


def test_no_feature_quality_note_in_institutional(
    synthetic_feature_history, feature_cols
):
    engine = HistoricalAnalogEngine(
        feature_cols=feature_cols, app_mode="v7_institutional"
    )
    query = synthetic_feature_history.tail(1).select(feature_cols).to_numpy()[0]
    anchor = synthetic_feature_history["effective_date"].max()
    result = engine.find_analogs_with_disagreement(
        synthetic_feature_history,
        query=query,
        anchor_date=anchor,
        dominant_state_id=1,
        k=20,
    )
    assert result.feature_quality_note is None


def test_lite_missing_features_constant():
    assert "earnings_revision_z" in LITE_MISSING_FEATURES
