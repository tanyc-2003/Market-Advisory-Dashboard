"""Tests for TraderCalibrationSystem (Phase 10)."""
from __future__ import annotations

import numpy as np
import polars as pl

from src.advisory.layer9_calibration.calibration import (
    CONFIDENCE_TO_PROB,
    ECE_WELL_CALIBRATED,
    THESIS_DRIFT_THRESHOLD,
    TraderCalibrationSystem,
)


def _well_calibrated_journal(n_per_band: int = 25, seed: int = 0) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for c, prob in CONFIDENCE_TO_PROB.items():
        wins = rng.random(n_per_band) < prob
        for w in wins:
            rows.append(
                {
                    "confidence_self": c,
                    "pnl_pct": 0.01 if w else -0.01,
                    "market_state_id": int(c % 3),
                    "thesis_validated": True,
                }
            )
    return pl.DataFrame(rows)


def test_insufficient_data_returns_status():
    cal = TraderCalibrationSystem()
    journal = pl.DataFrame({"confidence_self": [1, 2], "pnl_pct": [0.01, -0.02]})
    result = cal.evaluate(journal)
    assert result["status"] == "INSUFFICIENT_DATA"


def test_well_calibrated_trader_passes_threshold():
    cal = TraderCalibrationSystem()
    result = cal.evaluate(_well_calibrated_journal(n_per_band=80))
    assert result["status"] == "OK"
    assert result["ece"] < 0.10  # at least moderately calibrated


def test_overconfident_trader_fails_calibration():
    # All confidence=5 (predicted 0.85) but only 30% wins → high ECE.
    rng = np.random.default_rng(0)
    rows = []
    for _ in range(100):
        rows.append(
            {
                "confidence_self": 5,
                "pnl_pct": 0.01 if rng.random() < 0.30 else -0.01,
                "market_state_id": 1,
                "thesis_validated": True,
            }
        )
    cal = TraderCalibrationSystem()
    result = cal.evaluate(pl.DataFrame(rows))
    assert result["ece"] > ECE_WELL_CALIBRATED


def test_wilson_n_zero_returns_full_uncertainty():
    cal = TraderCalibrationSystem()
    lo, hi = cal._wilson_score(0, 0)
    assert lo == 0.0 and hi == 1.0


def test_regime_performance_excludes_null_states():
    rows = [
        {"confidence_self": 3, "pnl_pct": 0.01, "market_state_id": 1, "thesis_validated": True},
        {"confidence_self": 3, "pnl_pct": -0.01, "market_state_id": None, "thesis_validated": True},
    ]
    cal = TraderCalibrationSystem()
    journal = pl.DataFrame(
        rows,
        schema={
            "confidence_self": pl.Int64,
            "pnl_pct": pl.Float64,
            "market_state_id": pl.Int64,
            "thesis_validated": pl.Boolean,
        },
    )
    result = cal.compute_regime_performance(journal)
    assert 1 in result["regimes"]
    assert None not in result["regimes"]


def test_thesis_drift_detected_above_threshold():
    rows = [
        {
            "confidence_self": 3,
            "pnl_pct": -0.02,
            "market_state_id": 1,
            "thesis_validated": False,
        }
        for _ in range(THESIS_DRIFT_THRESHOLD + 1)
    ]
    cal = TraderCalibrationSystem()
    result = cal.detect_thesis_drift(pl.DataFrame(rows))
    assert result["warning"]
    assert result["n_invalidated_losses"] >= THESIS_DRIFT_THRESHOLD + 1


def test_thesis_drift_not_flagged_below_threshold():
    rows = [
        {
            "confidence_self": 3,
            "pnl_pct": -0.02,
            "market_state_id": 1,
            "thesis_validated": False,
        }
        for _ in range(THESIS_DRIFT_THRESHOLD - 1)
    ]
    cal = TraderCalibrationSystem()
    result = cal.detect_thesis_drift(pl.DataFrame(rows))
    assert not result["warning"]
