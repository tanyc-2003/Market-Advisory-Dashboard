"""Tests for the deflated Sharpe ratio (Phase 0c)."""
from __future__ import annotations

import pytest

from src.advisory.layer0_validation.audit_log import AuditLog
from src.advisory.layer0_validation.deflated_sharpe import (
    STATIC_TRIAL_FLOOR,
    deflated_sharpe,
)


def test_n_trials_floored_at_static_floor():
    log = AuditLog(":memory:")
    try:
        result = deflated_sharpe(
            observed_sharpe=1.0, skew=0.0, kurt=3.0, n_obs=500, audit_log=log
        )
    finally:
        log.close()
    assert result["n_trials_used"] == STATIC_TRIAL_FLOOR
    assert result["audit_trial_count"] == 0


def test_dsr_monotone_decreasing_in_trial_count():
    log_small = AuditLog(":memory:")
    log_big = AuditLog(":memory:")
    try:
        for _ in range(STATIC_TRIAL_FLOOR + 1000):
            log_big.record("layer", "fn")
        small = deflated_sharpe(
            observed_sharpe=1.2, skew=0.0, kurt=3.0, n_obs=500, audit_log=log_small
        )
        big = deflated_sharpe(
            observed_sharpe=1.2, skew=0.0, kurt=3.0, n_obs=500, audit_log=log_big
        )
    finally:
        log_small.close()
        log_big.close()
    assert big["deflated_sharpe"] <= small["deflated_sharpe"]


def test_high_observed_sharpe_gives_higher_dsr():
    log = AuditLog(":memory:")
    try:
        low = deflated_sharpe(0.5, 0.0, 3.0, 500, log)
        high = deflated_sharpe(2.0, 0.0, 3.0, 500, log)
    finally:
        log.close()
    assert high["deflated_sharpe"] > low["deflated_sharpe"]


def test_dsr_is_probability_in_unit_interval():
    log = AuditLog(":memory:")
    try:
        result = deflated_sharpe(1.0, 0.0, 3.0, 500, log)
    finally:
        log.close()
    assert 0.0 <= result["deflated_sharpe"] <= 1.0
