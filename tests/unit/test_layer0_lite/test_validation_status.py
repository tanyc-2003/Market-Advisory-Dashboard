"""V7_lite Phase 0: ValidationStatus + schema extensions."""
from __future__ import annotations

from datetime import date

import duckdb

from src.advisory.data_infra.schema import bootstrap_schema
from src.advisory.layer0_validation.report import (
    LiteBypassReason,
    ValidationReport,
    ValidationStatus,
)


def test_validation_report_backward_compatible():
    # No new fields supplied — must not raise.
    r = ValidationReport(layer_name="layer1", as_of=date(2024, 1, 1))
    assert r.app_mode == "v7_institutional"
    assert r.validation_status is None
    # Legacy 3-state status still works.
    assert r.status == "blocked"  # wf_sharpe<=0 -> blocked path


def test_lite_survivorship_status_value():
    assert ValidationStatus.LITE_SURVIVORSHIP.value == "lite_survivorship"
    assert ValidationStatus.VALIDATION_PAUSED_DATA_INTEGRITY.value == (
        "validation_paused_data_integrity"
    )


def test_status_property_returns_lite_survivorship():
    r = ValidationReport(
        layer_name="layer1",
        as_of=date(2024, 1, 1),
        app_mode="v7_lite",
        validation_status=ValidationStatus.LITE_SURVIVORSHIP,
        survivorship_audit="BYPASSED_LITE_MODE",
    )
    assert r.status == "lite_survivorship"


def test_lite_bypass_reasons_enum():
    assert LiteBypassReason.SURVIVORSHIP_AUDIT.value == "survivorship_audit"
    assert LiteBypassReason.PIT_DATA_REQUIRED.value == "pit_data_required"


def test_app_mode_column_added_to_audit_schema():
    conn = duckdb.connect(":memory:")
    bootstrap_schema(conn)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(backtest_executions)").fetchall()}
    assert "app_mode" in cols
    cols = {r[1] for r in conn.execute("PRAGMA table_info(llm_cache)").fetchall()}
    assert "app_mode" in cols


def test_hmm_model_registry_created():
    conn = duckdb.connect(":memory:")
    bootstrap_schema(conn)
    # Table exists and accepts an insert
    conn.execute(
        "INSERT INTO hmm_model_registry "
        "(model_id, app_mode, trained_at, validation_status) "
        "VALUES ('m1', 'v7_lite', now(), 'candidate')"
    )
    n = conn.execute("SELECT COUNT(*) FROM hmm_model_registry").fetchone()[0]
    assert n == 1


def test_yfinance_audit_table_created():
    conn = duckdb.connect(":memory:")
    bootstrap_schema(conn)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(yfinance_fetch_audit)").fetchall()}
    assert {"ticker", "status", "n_rows", "n_consec_gaps", "app_mode"}.issubset(cols)


def test_bootstrap_schema_idempotent():
    conn = duckdb.connect(":memory:")
    bootstrap_schema(conn)
    bootstrap_schema(conn)  # should be a no-op
    n = conn.execute("SELECT COUNT(*) FROM hmm_model_registry").fetchone()[0]
    assert n == 0
