"""Tests for AuditLog (Phase 0b)."""
from __future__ import annotations

from src.advisory.layer0_validation.audit_log import AuditLog


def test_counter_starts_at_zero():
    log = AuditLog(":memory:")
    try:
        assert log.trial_count() == 0
    finally:
        log.close()


def test_counter_increments_atomically():
    log = AuditLog(":memory:")
    try:
        for _ in range(5):
            log.record("layer0", "fn")
        assert log.trial_count() == 5
    finally:
        log.close()


def test_counter_survives_reconnect(tmp_path):
    db = tmp_path / "audit.duckdb"
    log = AuditLog(db)
    for _ in range(3):
        log.record("layer0", "fn")
    log.close()
    log2 = AuditLog(db)
    try:
        assert log2.trial_count() == 3
    finally:
        log2.close()


def test_record_returns_current_count():
    log = AuditLog(":memory:")
    try:
        assert log.record("layer0", "fn") == 1
        assert log.record("layer0", "fn") == 2
    finally:
        log.close()
