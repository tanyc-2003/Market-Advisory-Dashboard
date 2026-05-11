"""Tests for the realistic execution harness (Phase 0d)."""
from __future__ import annotations

from datetime import datetime, timedelta

import polars as pl
import pytest

from src.advisory.paper_trading.harness import RealisticExecutionHarness


def test_buy_fill_at_or_above_ask():
    h = RealisticExecutionHarness()
    r = h.simulate_fill("buy", bid=100.0, ask=100.10, order_size=100, adv=10000)
    assert r.fill_price >= 100.10


def test_sell_fill_at_or_below_bid():
    h = RealisticExecutionHarness()
    r = h.simulate_fill("sell", bid=100.0, ask=100.10, order_size=100, adv=10000)
    assert r.fill_price <= 100.0


def test_invalid_direction_raises():
    h = RealisticExecutionHarness()
    with pytest.raises(ValueError):
        h.simulate_fill("hold", bid=100.0, ask=100.10, order_size=100, adv=1000)


def test_friction_increases_slippage():
    h = RealisticExecutionHarness()
    calm = h.simulate_fill("buy", 100.0, 100.10, 100, 10000, vol_z=0.0, spread_z=0.0)
    stress = h.simulate_fill("buy", 100.0, 100.10, 100, 10000, vol_z=2.0, spread_z=2.0)
    assert stress.slippage_bps > calm.slippage_bps


def test_zero_friction_baseline_is_pure_spread_plus_impact():
    h = RealisticExecutionHarness()
    r = h.simulate_fill("buy", 100.0, 100.10, 100, 10000, vol_z=0.0, spread_z=0.0)
    assert r.friction_bps == 0.0
    assert r.slippage_bps > 0


def test_property_slippage_strictly_positive():
    h = RealisticExecutionHarness()
    for size in (10, 100, 1000):
        for vol_z in (0.0, 0.5, 2.0):
            r = h.simulate_fill("buy", 100.0, 100.10, size, 100_000, vol_z=vol_z)
            assert r.slippage_bps > 0


def test_vwap_handles_fewer_bars_than_horizon():
    h = RealisticExecutionHarness()
    bars = pl.DataFrame(
        {
            "bid": [100.0, 100.1, 100.2, 100.15, 100.05],
            "ask": [100.1, 100.2, 100.3, 100.25, 100.15],
            "volume": [1000.0, 1100.0, 950.0, 1050.0, 1200.0],
        }
    )
    result = h.simulate_vwap_execution(
        "buy", bars, order_size=500, horizon_minutes=20
    )
    assert result["n_slices_actual"] == 5
    assert result["n_slices_requested"] == 20
    assert result["avg_fill_price"] > 0
