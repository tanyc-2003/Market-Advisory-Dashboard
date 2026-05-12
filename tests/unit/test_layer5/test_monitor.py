"""Tests for IntradayFrictionMonitor (Phase 7)."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from src.advisory.layer5_stress.calendar import CalendarEvent
from src.advisory.layer5_stress.monitor import IntradayFrictionMonitor


def _baseline(seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = 60
    return pd.DataFrame(
        {
            "spread_bps": rng.normal(10, 1.5, n),
            "volume": rng.normal(1e6, 1e5, n),
            "realized_vol": rng.normal(0.15, 0.02, n),
        }
    )


def test_modified_z_score_zero_for_median():
    m = IntradayFrictionMonitor()
    arr = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    assert abs(m._modified_z_score(arr, 3.0)) < 1e-9


def test_modified_z_score_positive_above_median():
    m = IntradayFrictionMonitor()
    arr = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    assert m._modified_z_score(arr, 10.0) > 0


def test_mad_zero_baseline_returns_zero():
    m = IntradayFrictionMonitor()
    arr = np.array([5.0] * 10)
    assert m._modified_z_score(arr, 100.0) == 0.0


def test_suppression_returns_suppressed_status():
    cal = {date(2024, 3, 20): [CalendarEvent.FOMC_DAY]}
    monitor = IntradayFrictionMonitor(economic_calendar=cal)
    result = monitor.compute_friction_z_score(
        ticker="AAPL",
        on_date=date(2024, 3, 20),
        bucket="open",
        current_observation={"spread_bps": 100, "volume": 1e9, "realized_vol": 1.0},
        baseline=_baseline(),
    )
    assert result["status"] == "SUPPRESSED"


def test_alert_fires_when_z_above_threshold():
    monitor = IntradayFrictionMonitor()
    base = _baseline()
    # Construct a heavy outlier across all three channels
    result = monitor.compute_friction_z_score(
        ticker="AAPL",
        on_date=date(2024, 3, 19),
        bucket="open",
        current_observation={
            "spread_bps": 100.0,
            "volume": 5e6,
            "realized_vol": 0.5,
        },
        baseline=base,
    )
    assert result["alert"] is True


def test_insufficient_data_returns_status():
    monitor = IntradayFrictionMonitor()
    short = _baseline().head(5)
    result = monitor.compute_friction_z_score(
        ticker="AAPL",
        on_date=date(2024, 3, 19),
        bucket="open",
        current_observation={"spread_bps": 10, "volume": 1e6, "realized_vol": 0.15},
        baseline=short,
    )
    assert result["status"] == "INSUFFICIENT_DATA"


def test_get_vol_z_cached_for_layer2_wiring():
    monitor = IntradayFrictionMonitor()
    monitor.compute_friction_z_score(
        ticker="AAPL",
        on_date=date(2024, 3, 19),
        bucket="open",
        current_observation={"spread_bps": 12, "volume": 5e6, "realized_vol": 0.18},
        baseline=_baseline(),
    )
    # After a normal compute, vol_z is cached and non-zero.
    assert monitor.get_vol_z("AAPL") != 0.0
    # Unknown ticker defaults to 0.
    assert monitor.get_vol_z("ZZZZ") == 0.0
