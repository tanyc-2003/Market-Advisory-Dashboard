"""V7_lite Phase 12: Harness CS/Amihud separation assertion."""
from __future__ import annotations

import pytest

from src.advisory.paper_trading.harness import RealisticExecutionHarness


def test_amihud_alone_raises_in_lite_mode():
    h = RealisticExecutionHarness()
    with pytest.raises(AssertionError):
        h.simulate_fill(
            direction="buy",
            bid=100.0,
            ask=100.10,
            order_size=100,
            adv=10_000,
            friction_proxy={"amihud_z": 1.5},  # missing cs_spread_execution_proxy
            app_mode="v7_lite",
        )


def test_cs_spread_proxy_accepted_in_lite_mode():
    h = RealisticExecutionHarness()
    r = h.simulate_fill(
        direction="buy",
        bid=100.0,
        ask=100.10,
        order_size=100,
        adv=10_000,
        friction_proxy={
            "cs_spread_execution_proxy": 0.002,
            "amihud_z": 1.5,
        },
        app_mode="v7_lite",
    )
    assert r.fill_price >= 100.10  # adverse-side invariant still holds


def test_institutional_mode_does_not_enforce_cs_proxy_key():
    h = RealisticExecutionHarness()
    # Institutional mode: pass legacy spread_z/volume_z keys.
    r = h.simulate_fill(
        direction="sell",
        bid=100.0,
        ask=100.10,
        order_size=100,
        adv=10_000,
        friction_proxy={"spread_z": 0.5, "volume_z": 0.5},
        app_mode="v7_institutional",
    )
    assert r.fill_price <= 100.0


def test_no_friction_proxy_no_assertion():
    h = RealisticExecutionHarness()
    r = h.simulate_fill(
        direction="buy", bid=100.0, ask=100.10, order_size=100, adv=10_000
    )
    assert r.fill_price >= 100.10
