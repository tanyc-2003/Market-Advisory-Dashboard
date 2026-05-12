"""Tests for ContinuousValidator (Phase 0c)."""
from __future__ import annotations

import numpy as np
import polars as pl

from src.advisory.layer0_validation.continuous_validator import ContinuousValidator


def _log(n: int, mean: float = 0.0005, std: float = 0.01) -> pl.DataFrame:
    rng = np.random.default_rng(0)
    return pl.DataFrame({"pnl_pct": rng.normal(mean, std, size=n)})


def test_insufficient_data_returns_status():
    cv = ContinuousValidator()
    result = cv.evaluate("layer1", 1.0, _log(30))
    assert result["status"] == "INSUFFICIENT_PAPER_DATA"
    assert result["demote_to_research"] is False


def test_no_demote_when_within_threshold():
    cv = ContinuousValidator()
    # Construct a return stream whose annualised Sharpe is ~1.0 (matches
    # pre_deployment_sharpe), so divergence stays well inside the 30%
    # threshold.
    rng = np.random.default_rng(0)
    target_sharpe = 1.0
    std = 0.01
    mean = target_sharpe * std / float(np.sqrt(252))
    log = pl.DataFrame({"pnl_pct": rng.normal(mean, std, size=200)})
    result = cv.evaluate("layer1", 1.0, log)
    assert not result["demote_to_research"]


def test_demote_when_divergence_exceeds_threshold():
    cv = ContinuousValidator()
    # Live Sharpe is near 0; pre-deployment is 1.0 -> divergence ~100%
    log = pl.DataFrame({"pnl_pct": np.full(120, 1e-6)})
    result = cv.evaluate("layer1", 1.0, log)
    assert result["demote_to_research"]
