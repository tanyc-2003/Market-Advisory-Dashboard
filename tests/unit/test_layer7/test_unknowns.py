"""Tests for the unknowns generator (Phase 8)."""
from __future__ import annotations

from src.advisory.layer7_hygiene.unknowns import (
    STRUCTURAL_CHANGE_UNKNOWN,
    generate_unknowns_section,
)


def test_structural_change_always_appended():
    out = generate_unknowns_section(
        analog_result=None,
        n_analogs=30,
        dimensionality_passed=True,
        survivorship_passed=True,
    )
    assert out[-1] == STRUCTURAL_CHANGE_UNKNOWN


def test_low_analog_count_adds_warning():
    out = generate_unknowns_section(
        analog_result=None,
        n_analogs=3,
        dimensionality_passed=True,
        survivorship_passed=True,
    )
    assert any("Only 3 historical analogs" in s for s in out)


def test_dimensionality_failure_adds_warning():
    out = generate_unknowns_section(
        analog_result=None,
        n_analogs=50,
        dimensionality_passed=False,
        survivorship_passed=True,
    )
    assert any("dimensionality" in s.lower() for s in out)


def test_survivorship_failure_adds_warning():
    out = generate_unknowns_section(
        analog_result=None,
        n_analogs=50,
        dimensionality_passed=True,
        survivorship_passed=False,
    )
    assert any("survivorship" in s.lower() for s in out)
