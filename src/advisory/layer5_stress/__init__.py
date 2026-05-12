"""Layer 5 — Market Stress & Abnormality Monitor.

Implementation order (architecture §21): build Layer 6 first, then 5,
because Layer 5's ``vol_z`` is consumed by :class:`HistoricalAnalogEngine`
(Layer 2) as a plain float — no circular import.
"""
from .calendar import (
    CalendarEvent,
    SUPPRESSION_RULES,
    is_suppression_active,
    load_economic_calendar,
)
from .lite_monitor import (
    AMIHUD_DOLLAR_VOLUME_FLOOR,
    LiteFrictionMonitor,
    amihud_illiquidity,
    corwin_schultz_spread,
)
from .monitor import IntradayFrictionMonitor


def create_friction_monitor(
    app_mode: str, economic_calendar: dict | None = None
):
    """Factory: pick the right monitor for the active mode.

    Architecture §11 mandates a clean separation so the wrong monitor
    can't be silently substituted.
    """
    if app_mode == "v7_lite":
        return LiteFrictionMonitor(economic_calendar)
    return IntradayFrictionMonitor(economic_calendar)


__all__ = [
    "AMIHUD_DOLLAR_VOLUME_FLOOR",
    "CalendarEvent",
    "IntradayFrictionMonitor",
    "LiteFrictionMonitor",
    "SUPPRESSION_RULES",
    "amihud_illiquidity",
    "corwin_schultz_spread",
    "create_friction_monitor",
    "is_suppression_active",
    "load_economic_calendar",
]
