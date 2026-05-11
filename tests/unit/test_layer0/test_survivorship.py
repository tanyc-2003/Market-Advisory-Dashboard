"""Tests for SurvivorshipAuditor (Phase 0a)."""
from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from src.advisory.layer0_validation.survivorship import (
    SurvivorshipAuditError,
    SurvivorshipAuditor,
)


def _delisted(tickers: list[str], in_window: bool = True) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "ticker": tickers,
            "termination_date": [
                date(2021, 6, 15) if in_window else date(2010, 1, 1)
                for _ in tickers
            ],
        }
    )


def test_audit_passes_when_coverage_above_floor():
    auditor = SurvivorshipAuditor(coverage_floor=0.95)
    delisted = _delisted([f"DEL{i}" for i in range(20)])
    live = pl.DataFrame({"ticker": [f"DEL{i}" for i in range(20)] + ["A", "B"]})
    result = auditor.audit(
        live, delisted, window_start=date(2020, 1, 1), window_end=date(2022, 12, 31)
    )
    assert result["passed"]
    assert result["coverage"] == pytest.approx(1.0)


def test_audit_fails_when_coverage_below_floor():
    auditor = SurvivorshipAuditor(coverage_floor=0.95)
    delisted = _delisted([f"DEL{i}" for i in range(10)])
    # Only 7 of 10 found -> coverage 0.70 < 0.95
    live = pl.DataFrame({"ticker": [f"DEL{i}" for i in range(7)]})
    result = auditor.audit(
        live, delisted, window_start=date(2020, 1, 1), window_end=date(2022, 12, 31)
    )
    assert not result["passed"]
    assert "FAIL" in result["note"]


def test_raise_if_failed_raises():
    auditor = SurvivorshipAuditor(coverage_floor=0.95)
    delisted = _delisted([f"DEL{i}" for i in range(10)])
    live = pl.DataFrame({"ticker": [f"DEL{i}" for i in range(2)]})
    result = auditor.audit(
        live, delisted, window_start=date(2020, 1, 1), window_end=date(2022, 12, 31)
    )
    with pytest.raises(SurvivorshipAuditError):
        SurvivorshipAuditor.raise_if_failed(result)


def test_coverage_floor_cannot_be_below_08():
    with pytest.raises(ValueError):
        SurvivorshipAuditor(coverage_floor=0.5)


def test_property_coverage_threshold():
    # For any random coverage in [0,1], passed == (coverage >= floor)
    import random

    random.seed(0)
    floor = 0.9
    auditor = SurvivorshipAuditor(coverage_floor=floor)
    for _ in range(30):
        n_total = 10
        # Build delisted tickers in-window
        delisted = _delisted([f"X{i}" for i in range(n_total)])
        n_found = random.randint(0, n_total)
        live = pl.DataFrame({"ticker": [f"X{i}" for i in range(n_found)]})
        result = auditor.audit(
            live,
            delisted,
            window_start=date(2020, 1, 1),
            window_end=date(2022, 12, 31),
        )
        expected = (n_found / n_total) >= floor
        assert result["passed"] == expected
