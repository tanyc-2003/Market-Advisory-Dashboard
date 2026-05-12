"""Tests for the economic calendar / suppression rules (Phase 7)."""
from __future__ import annotations

from datetime import date

from src.advisory.layer5_stress.calendar import (
    CalendarEvent,
    is_suppression_active,
)


def test_suppression_active_on_fomc_day():
    cal = {date(2024, 3, 20): [CalendarEvent.FOMC_DAY]}
    suppressed, reason = is_suppression_active(date(2024, 3, 20), cal)
    assert suppressed
    assert reason and "FOMC" in reason


def test_suppression_inactive_on_normal_day():
    cal = {date(2024, 3, 20): [CalendarEvent.FOMC_DAY]}
    suppressed, reason = is_suppression_active(date(2024, 3, 19), cal)
    assert not suppressed
    assert reason is None


def test_empty_calendar_no_suppression():
    suppressed, reason = is_suppression_active(date(2024, 3, 20), {})
    assert not suppressed
    assert reason is None


def test_multiple_events_same_day_still_suppressed():
    cal = {date(2024, 3, 20): [CalendarEvent.FOMC_DAY, CalendarEvent.CPI_DAY]}
    suppressed, _ = is_suppression_active(date(2024, 3, 20), cal)
    assert suppressed


def test_accepts_raw_strings_in_calendar():
    cal = {date(2024, 3, 20): ["fomc_day"]}
    suppressed, _ = is_suppression_active(date(2024, 3, 20), cal)
    assert suppressed
