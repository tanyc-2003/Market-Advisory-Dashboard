"""V7_lite Phase 8: Binomial wipeout injection properties."""
from __future__ import annotations

import numpy as np

from config.settings import settings
from src.advisory.layer10_sizing.lite_diagnostics import (
    inject_synthetic_wipeouts,
    sizing_diagnostics_lite,
)


def test_binomial_draw_not_deterministic_floor():
    rng = np.random.default_rng(42)
    counts: list[int] = []
    for _ in range(2000):
        arr = np.zeros(50)
        _, n_inj = inject_synthetic_wipeouts(
            arr,
            annual_impairment_rate=0.02,
            period_days=10,
            rng=rng,
        )
        counts.append(n_inj)
    mean = float(np.mean(counts))
    expected = 50 * 0.02 * (10 / 252)  # ≈ 0.0397
    # A deterministic floor of 1 would yield mean == 1.0 — far above 0.04.
    assert mean < 0.30
    # Many draws should return zero.
    zero_frac = sum(1 for c in counts if c == 0) / len(counts)
    assert zero_frac > 0.85


def test_no_injection_returns_input_when_zero_drawn():
    rng = np.random.default_rng(0)
    arr = np.array([0.01, 0.02, -0.01, 0.03])
    out, n = inject_synthetic_wipeouts(
        arr,
        annual_impairment_rate=0.0,
        period_days=10,
        rng=rng,
    )
    assert n == 0
    np.testing.assert_array_equal(out, arr)


def test_wipeout_value_matches_constant():
    # Force a draw by passing rate=1.0 (every entry becomes a wipeout).
    rng = np.random.default_rng(0)
    arr = np.zeros(5)
    out, n = inject_synthetic_wipeouts(
        arr,
        annual_impairment_rate=1.0,
        period_days=252,  # rate * period/252 = 1.0
        synthetic_wipeout_return=-0.99,
        rng=rng,
    )
    assert n == 5
    # The 5 injected entries should all equal -0.99.
    assert (out[len(arr):] == -0.99).all()


def test_sizing_lite_carries_bias_note_and_n_injected():
    rng = np.random.default_rng(0)
    returns = np.concatenate([np.full(60, 0.04), np.full(40, -0.02)])
    result = sizing_diagnostics_lite(
        analog_returns=returns,
        state_uncertainty=0.1,
        hmm_analog_overlap_pct=0.9,
        rng=rng,
    )
    assert "n_injected" in result
    assert "survivorship_bias_note" in result
    assert "synthetic wipeout" in result["survivorship_bias_note"].lower()
    assert result["app_mode"] == "v7_lite"


def test_kelly_cap_preserved_through_wrapper():
    rng = np.random.default_rng(0)
    # Strongly profitable distribution → raw Kelly would blow past 0.20.
    returns = np.concatenate([np.full(95, 0.10), np.full(5, -0.001)])
    result = sizing_diagnostics_lite(
        analog_returns=returns,
        state_uncertainty=0.0,
        hmm_analog_overlap_pct=1.0,
        rng=rng,
    )
    for key in (
        "raw_kelly",
        "haircut_kelly_standard",
        "haircut_kelly_regime",
        "displayed_kelly",
    ):
        assert result[key] <= settings.kelly_absolute_cap + 1e-9


def test_survivorship_win_rate_adjustment_removed_from_codebase():
    """The architecture forbids ``SURVIVORSHIP_WIN_RATE_ADJUSTMENT`` — it
    modified the wrong Kelly term.  Verify it doesn't exist anywhere."""
    import importlib

    mod = importlib.import_module("src.advisory.layer10_sizing.diagnostics")
    assert not hasattr(mod, "SURVIVORSHIP_WIN_RATE_ADJUSTMENT")
    mod_lite = importlib.import_module("src.advisory.layer10_sizing.lite_diagnostics")
    assert not hasattr(mod_lite, "SURVIVORSHIP_WIN_RATE_ADJUSTMENT")
