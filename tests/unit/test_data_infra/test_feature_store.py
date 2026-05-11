"""Tests for FeatureStore (Phase 1)."""
from __future__ import annotations

from datetime import date

import polars as pl


def _row(t, eff, kn, name, val):
    return {
        "ticker": t,
        "effective_date": eff,
        "knowledge_date": kn,
        "feature_name": name,
        "feature_value": val,
    }


def test_pit_retrieval_excludes_future_knowledge(feature_store):
    df = pl.DataFrame(
        [
            _row("AAPL", date(2024, 1, 5), date(2024, 1, 6), "ret_1d", 0.01),
        ]
    )
    feature_store.write_features(df, source="test", version="v1")
    result = feature_store.get_feature_pit(
        "AAPL", "ret_1d", prediction_date=date(2024, 1, 5)
    )
    assert result is None  # knowledge_date 1/6 > prediction 1/5


def test_pit_retrieval_returns_most_recent_value(feature_store):
    df = pl.DataFrame(
        [
            _row("AAPL", date(2024, 1, 5), date(2024, 1, 5), "ret_1d", 0.01),
            _row("AAPL", date(2024, 1, 5), date(2024, 1, 8), "ret_1d", 0.02),
        ]
    )
    feature_store.write_features(df, source="test", version="v1")
    on_jan_7 = feature_store.get_feature_pit(
        "AAPL", "ret_1d", prediction_date=date(2024, 1, 7)
    )
    on_jan_9 = feature_store.get_feature_pit(
        "AAPL", "ret_1d", prediction_date=date(2024, 1, 9)
    )
    assert on_jan_7 == 0.01  # only kn=1/5 < 1/7
    assert on_jan_9 == 0.02  # latest is kn=1/8 < 1/9


def test_write_read_roundtrip(feature_store):
    rows = [
        _row("X", date(2024, 1, d), date(2024, 1, d), "ret_1d", 0.001 * d)
        for d in range(1, 11)
    ]
    df = pl.DataFrame(rows)
    n = feature_store.write_features(df, source="test", version="v1")
    assert n == 10


def test_cache_snapshot_roundtrip(feature_store):
    df = pl.DataFrame({"x": [1, 2, 3], "y": [0.1, 0.2, 0.3]})
    feature_store.cache_snapshot(df, "snap1")
    loaded = feature_store.load_snapshot("snap1")
    assert loaded is not None
    assert loaded.shape == (3, 2)
