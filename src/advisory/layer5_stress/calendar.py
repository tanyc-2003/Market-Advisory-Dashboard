"""Economic-calendar driven suppression rules.

Friction alerts are silently suppressed during scheduled macro events
where elevated z-scores carry no signal.
"""
from __future__ import annotations

import json
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Iterable

import structlog

logger = structlog.get_logger(__name__)


class CalendarEvent(str, Enum):
    """Architecture-pinned set of recognised calendar event types."""

    FOMC_DAY = "fomc_day"
    CPI_DAY = "cpi_day"
    NFP_DAY = "nfp_day"
    GDP_DAY = "gdp_day"
    OPTIONS_EXPIRY = "options_expiry"
    QUARTER_END = "quarter_end"


SUPPRESSION_RULES: dict[CalendarEvent, str] = {
    CalendarEvent.FOMC_DAY: "FOMC day — friction alerts suppressed",
    CalendarEvent.CPI_DAY: "CPI release — friction alerts suppressed",
    CalendarEvent.NFP_DAY: "NFP release — friction alerts suppressed",
    CalendarEvent.GDP_DAY: "GDP release — friction alerts suppressed",
    CalendarEvent.OPTIONS_EXPIRY: "Options expiry — friction alerts suppressed",
    CalendarEvent.QUARTER_END: "Quarter-end — friction alerts suppressed",
}


def _normalise(events: Iterable) -> list[CalendarEvent]:
    out: list[CalendarEvent] = []
    for e in events:
        if isinstance(e, CalendarEvent):
            out.append(e)
        else:
            try:
                out.append(CalendarEvent(str(e)))
            except ValueError:
                logger.warning("calendar_unknown_event", event=str(e))
    return out


def is_suppression_active(
    on_date: date,
    economic_calendar: dict[date, list[CalendarEvent]],
) -> tuple[bool, str | None]:
    """Return ``(suppressed, reason)`` for a given trading date."""
    events = economic_calendar.get(on_date)
    if not events:
        return False, None
    normalised = _normalise(events)
    for ev in normalised:
        if ev in SUPPRESSION_RULES:
            return True, SUPPRESSION_RULES[ev]
    return False, None


def load_economic_calendar(
    path: Path | None = None,
) -> dict[date, list[CalendarEvent]]:
    """Load the economic calendar from a JSON file.

    Format: ``{"YYYY-MM-DD": ["fomc_day", "cpi_day"], ...}``.
    ``path=None`` returns an empty calendar (no suppression).
    """
    if path is None:
        return {}
    if not path.exists():
        logger.warning("calendar_file_not_found", path=str(path))
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: dict[date, list[CalendarEvent]] = {}
    for ds, events in raw.items():
        try:
            d = date.fromisoformat(ds)
        except ValueError:
            logger.warning("calendar_bad_date", entry=ds)
            continue
        out[d] = _normalise(events)
    return out
