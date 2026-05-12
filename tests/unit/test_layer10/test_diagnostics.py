"""Tests for sizing_diagnostics (Phase 11 / Layer 10)."""
from __future__ import annotations

import numpy as np
import pytest

from src.advisory.layer10_sizing.diagnostics import (
    KELLY_ABSOLUTE_CAP,
    KELLY_LOW_SAMPLE_THRESHOLD,
    MIN_ANALOGS,
    SIZING_NOTE,
    sizing_diagnostics,
)


def _winning_distribution(seed: int = 0, n: int = 200) -> np.ndarray:
    rng = np.random.default_rng(seed)
    wins = rng.normal(0.04, 0.01, size=int(n * 0.65))
    losses = rng.normal(-0.02, 0.005, size=n - len(wins))
    return np.concatenate([wins, losses])


def test_insufficient_analogs_returns_status():
    result = sizing_diagnostics(
        analog_returns=[0.01] * (MIN_ANALOGS - 1),
        state_uncertainty=0.2,
        hmm_analog_overlap_pct=0.8,
    )
    assert result["status"] == "INSUFFICIENT_ANALOGS"
    assert result["n"] == MIN_ANALOGS - 1


def test_kelly_capped_at_absolute_cap():
    # Construct an unambiguously profitable sample (high win rate,
    # large payoff ratio) so raw Kelly would exceed the cap.
    rng = np.random.default_rng(0)
    returns = np.concatenate(
        [rng.normal(0.10, 0.005, 95), rng.normal(-0.001, 0.0005, 5)]
    )
    result = sizing_diagnostics(
        analog_returns=returns,
        state_uncertainty=0.0,
        hmm_analog_overlap_pct=1.0,
    )
    assert result["status"] == "OK"
    assert result["raw_kelly"] <= KELLY_ABSOLUTE_CAP
    assert result["haircut_kelly_standard"] <= KELLY_ABSOLUTE_CAP
    assert result["haircut_kelly_regime"] <= KELLY_ABSOLUTE_CAP
    assert result["displayed_kelly"] <= KELLY_ABSOLUTE_CAP


def test_es5_used_as_loss_term_not_mean_loss():
    # Construct a heavy-tailed sample where ES_5 is much more negative
    # than the mean of losses.  The Kelly loss term must equal |ES_5|.
    # Sample size 200: 5th-pct lands at index 10 → must sit inside the
    # tail block, so use 20 tail losses (10%).
    wins = [0.02] * 100
    losses_normal = [-0.005] * 80
    losses_tail = [-0.50] * 20
    arr = np.array(wins + losses_normal + losses_tail)
    result = sizing_diagnostics(
        analog_returns=arr,
        state_uncertainty=0.0,
        hmm_analog_overlap_pct=1.0,
    )
    # ES_5 (5th pct of full sample of 200) falls inside the tail block.
    assert result["es_5"] < -0.4
    # The Kelly loss term must equal |ES_5|, not the mean of losses
    # (which would be ≈ 0.103).
    assert result["avg_loss"] == pytest.approx(abs(result["es_5"]))


def test_regime_adjusted_haircut_smaller_than_standard():
    rng = np.random.default_rng(1)
    returns = np.concatenate(
        [rng.normal(0.04, 0.01, 130), rng.normal(-0.02, 0.005, 70)]
    )
    result = sizing_diagnostics(
        analog_returns=returns,
        state_uncertainty=0.3,
        hmm_analog_overlap_pct=0.6,
    )
    # 0.5 * (1-0.3) * min(1, 0.9) = 0.5 * 0.7 * 0.9 = 0.315 < 0.5
    assert result["haircut_kelly_regime"] < result["haircut_kelly_standard"]


def test_zero_confidence_produces_zero_regime_kelly():
    returns = _winning_distribution()
    result = sizing_diagnostics(
        analog_returns=returns,
        state_uncertainty=1.0,
        hmm_analog_overlap_pct=0.0,
    )
    assert result["effective_haircut"] == 0.0
    assert result["haircut_kelly_regime"] == 0.0
    assert result["displayed_kelly"] == 0.0


def test_low_sample_warning_fires_below_threshold():
    rng = np.random.default_rng(0)
    returns = np.concatenate(
        [rng.normal(0.03, 0.01, 30), rng.normal(-0.02, 0.005, 20)]
    )
    assert len(returns) < KELLY_LOW_SAMPLE_THRESHOLD
    result = sizing_diagnostics(
        analog_returns=returns,
        state_uncertainty=0.1,
        hmm_analog_overlap_pct=0.9,
    )
    assert any("Sample fragile" in w for w in result["warnings"])


def test_note_contains_exact_architecture_language():
    result = sizing_diagnostics(
        analog_returns=_winning_distribution(),
        state_uncertainty=0.2,
        hmm_analog_overlap_pct=0.8,
    )
    assert result["note"] == SIZING_NOTE
    assert "tail-aware" in SIZING_NOTE
    assert "20%" in SIZING_NOTE


def test_property_all_kelly_outputs_in_unit_cap_interval():
    rng = np.random.default_rng(42)
    for _ in range(20):
        n = int(rng.integers(MIN_ANALOGS, 500))
        win_rate = float(rng.uniform(0.05, 0.95))
        n_wins = int(n * win_rate)
        wins = rng.normal(0.04, 0.01, n_wins)
        losses = rng.normal(-0.02, 0.005, n - n_wins)
        returns = np.concatenate([wins, losses])
        result = sizing_diagnostics(
            analog_returns=returns,
            state_uncertainty=float(rng.uniform(0, 1)),
            hmm_analog_overlap_pct=float(rng.uniform(0, 1)),
        )
        for key in (
            "raw_kelly",
            "haircut_kelly_standard",
            "haircut_kelly_regime",
            "displayed_kelly",
        ):
            value = result.get(key, 0.0)
            assert 0.0 <= value <= KELLY_ABSOLUTE_CAP, f"{key}={value} OOB"


def test_no_downside_tail_falls_back_to_mean_loss():
    # Construct a sample with positive ES_5 (no losses in the 5% tail
    # of the full distribution) but a handful of small losses overall.
    arr = np.concatenate([np.full(195, 0.01), np.full(5, -0.001)])
    result = sizing_diagnostics(
        analog_returns=arr,
        state_uncertainty=0.0,
        hmm_analog_overlap_pct=1.0,
    )
    # ES_5 here is positive (5th pct of the full distribution).
    assert result["es_5"] >= 0
    # Loss term falls back to |mean(losses)| = 0.001.
    assert result["avg_loss"] == pytest.approx(0.001, rel=1e-6)
    assert any("ES₅" in w for w in result["warnings"])


def test_no_winning_analogs_returns_zero():
    returns = np.full(50, -0.01)
    result = sizing_diagnostics(
        analog_returns=returns,
        state_uncertainty=0.0,
        hmm_analog_overlap_pct=1.0,
    )
    assert result["displayed_kelly"] == 0.0
    assert result["raw_kelly"] == 0.0
