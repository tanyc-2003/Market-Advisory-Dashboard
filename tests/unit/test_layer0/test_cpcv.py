"""Tests for CPCVRunner + WalkForwardCV (Phase 0c)."""
from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from src.advisory.layer0_validation.audit_log import AuditLog
from src.advisory.layer0_validation.cpcv import CPCVRunner
from src.advisory.layer0_validation.walk_forward import WalkForwardCV


def _flat_history(n: int) -> pl.DataFrame:
    rng = np.random.default_rng(0)
    return pl.DataFrame(
        {
            "ret_1d": rng.normal(0.0, 0.01, size=n),
            "feature": rng.normal(0.0, 1.0, size=n),
        }
    )


def _trivial_signal(train: pl.DataFrame, test: pl.DataFrame) -> np.ndarray:
    return test["ret_1d"].to_numpy()


def test_fallback_when_insufficient_data():
    log = AuditLog(":memory:")
    try:
        runner = CPCVRunner(log)
        result = runner.run(_flat_history(100), _trivial_signal)
    finally:
        log.close()
    assert result.get("fallback") == "walk_forward"


def test_embargo_floor_enforced():
    log = AuditLog(":memory:")
    try:
        with pytest.raises(ValueError):
            CPCVRunner(log, embargo_days=200)
    finally:
        log.close()


def test_walk_forward_returns_finite_sharpes_when_data_sufficient():
    log = AuditLog(":memory:")
    try:
        wf = WalkForwardCV(log, embargo_days=504)
        result = wf.run(_flat_history(4000), _trivial_signal, n_splits=3)
    finally:
        log.close()
    assert result["status"] == "OK"
    assert result["n_paths"] >= 1
    assert all(np.isfinite(s) for s in result["sharpes"])


def test_walk_forward_records_to_audit():
    log = AuditLog(":memory:")
    try:
        wf = WalkForwardCV(log)
        before = log.trial_count()
        wf.run(_flat_history(4000), _trivial_signal, n_splits=3)
        after = log.trial_count()
    finally:
        log.close()
    assert after == before + 1
