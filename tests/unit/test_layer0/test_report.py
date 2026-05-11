"""Tests for ValidationReport + validate_layer + requires_production."""
from __future__ import annotations

from datetime import date

import pytest

from src.advisory.layer0_validation.report import (
    ValidationGateError,
    ValidationReport,
    requires_production,
    validate_layer,
)


def _passing_report(name: str = "layer1") -> ValidationReport:
    return ValidationReport(
        layer_name=name,
        as_of=date(2024, 1, 1),
        walk_forward_sharpe=1.0,
        walk_forward_ece=0.03,
        cpcv_p30_sharpe=0.6,
        cpcv_p50_sharpe=0.9,
        cpcv_path_count=15,
        deflated_sharpe=0.97,
        survivorship_audit="PASSED",
        survivorship_coverage=0.99,
    )


def test_status_blocked_when_survivorship_failed():
    r = _passing_report()
    r.survivorship_audit = "FAILED"
    assert r.status == "blocked"


def test_status_blocked_when_negative_walk_forward_sharpe():
    r = _passing_report()
    r.walk_forward_sharpe = -0.5
    assert r.status == "blocked"


def test_validate_layer_passes_clean_report():
    r = _passing_report()
    status = validate_layer(r)
    assert status == "production"
    assert r.production_ready


def test_validate_layer_research_preview_on_dsr_fail():
    r = _passing_report()
    r.deflated_sharpe = 0.2
    status = validate_layer(r)
    assert status == "research_preview"
    assert not r.production_ready


def test_requires_production_raises_when_not_ready():
    r = _passing_report()
    r.production_ready = False
    r.rationale = "test"

    @requires_production(lambda: r)
    def f():
        return 1

    with pytest.raises(ValidationGateError):
        f()


def test_requires_production_passes_when_ready():
    r = _passing_report()
    validate_layer(r)

    @requires_production(lambda: r)
    def f():
        return 1

    assert f() == 1


def test_to_dashboard_dict_is_json_safe():
    r = _passing_report()
    validate_layer(r)
    d = r.to_dashboard_dict()
    assert d["status"] == "production"
    assert d["as_of"] == "2024-01-01"
