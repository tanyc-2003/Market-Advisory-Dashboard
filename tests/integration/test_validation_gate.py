"""End-to-end: Layer 0 sign-off behaves as the architecture requires."""
from __future__ import annotations

from datetime import date

import pytest

from src.advisory.layer0_validation.report import (
    ValidationGateError,
    ValidationReport,
    requires_production,
    validate_layer,
)


def _baseline() -> ValidationReport:
    return ValidationReport(
        layer_name="layer1",
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


def test_failing_survivorship_blocks():
    r = _baseline()
    r.survivorship_audit = "FAILED"
    validate_layer(r)
    assert r.status == "blocked"


def test_passing_report_is_production_ready():
    r = _baseline()
    validate_layer(r)
    assert r.status == "production"
    assert r.production_ready


def test_walk_forward_pass_but_dsr_fail_is_research_preview():
    r = _baseline()
    r.deflated_sharpe = 0.10
    validate_layer(r)
    assert r.status == "research_preview"


def test_decorator_blocks_non_production_call():
    r = _baseline()
    r.production_ready = False
    r.rationale = "demo"

    @requires_production(lambda: r)
    def f():
        return "ok"

    with pytest.raises(ValidationGateError):
        f()
