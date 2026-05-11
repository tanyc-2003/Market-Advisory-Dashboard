"""Tests for FUNDAMENTAL_LAGS / get_lag."""
from __future__ import annotations

from src.advisory.data_infra.lag import FUNDAMENTAL_LAGS, get_lag


def test_unknown_feature_defaults_to_one():
    assert get_lag("mystery_feature_x") == 1


def test_realtime_features_have_zero_lag():
    assert get_lag("ret_1d") == 0


def test_earnings_revision_lagged_three_days():
    assert get_lag("earnings_revision_z") == 3


def test_all_known_features_return_consistent_values():
    for name, lag in FUNDAMENTAL_LAGS.items():
        assert get_lag(name) == lag
