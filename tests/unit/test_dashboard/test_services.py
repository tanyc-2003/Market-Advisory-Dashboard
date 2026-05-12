"""Tests for the dashboard service-layer helpers (Phase 12)."""
from __future__ import annotations

from datetime import date

import duckdb
import pytest

from src.advisory.dashboard.services import (
    get_validation_report,
    is_data_stale,
    list_layer_status_rows,
    persist_validation_report,
)
from src.advisory.data_infra.schema import bootstrap_schema
from src.advisory.layer0_validation.report import ValidationReport, validate_layer


@pytest.fixture
def conn():
    c = duckdb.connect(":memory:")
    bootstrap_schema(c)
    yield c
    c.close()


def _passing_report(layer: str = "layer1") -> ValidationReport:
    r = ValidationReport(
        layer_name=layer,
        as_of=date(2024, 1, 1),
        walk_forward_sharpe=1.0,
        walk_forward_ece=0.03,
        cpcv_p30_sharpe=0.6,
        deflated_sharpe=0.97,
        survivorship_audit="PASSED",
        survivorship_coverage=0.99,
    )
    validate_layer(r)
    return r


def test_persist_and_load_round_trip(conn):
    persist_validation_report(conn, _passing_report("layer1"))
    loaded = get_validation_report(conn, "layer1")
    assert loaded is not None
    assert loaded.status == "production"
    assert loaded.walk_forward_sharpe == 1.0


def test_load_returns_none_for_unknown_layer(conn):
    assert get_validation_report(conn, "layer99") is None


def test_list_layer_status_rows_includes_no_report_rows(conn):
    rows = list_layer_status_rows(conn, layer_names=["layer1", "layer2"])
    assert {r["layer"] for r in rows} == {"layer1", "layer2"}
    for r in rows:
        assert r["status"] == "no_report"


def test_list_layer_status_rows_reflects_persisted_status(conn):
    persist_validation_report(conn, _passing_report("layer1"))
    rows = list_layer_status_rows(conn, layer_names=["layer1", "layer2"])
    by_layer = {r["layer"]: r for r in rows}
    assert by_layer["layer1"]["status"] == "production"
    assert by_layer["layer2"]["status"] == "no_report"


def test_is_data_stale_two_business_days():
    # Friday, then Monday is 1 business day later; Tuesday is 2; Wednesday is 3.
    fri = date(2024, 3, 1)
    mon = date(2024, 3, 4)
    tue = date(2024, 3, 5)
    wed = date(2024, 3, 6)
    assert is_data_stale(fri, mon) is False  # 1 BD apart
    assert is_data_stale(fri, tue) is False  # exactly 2 BDs
    assert is_data_stale(fri, wed) is True   # 3 BDs apart -> stale
