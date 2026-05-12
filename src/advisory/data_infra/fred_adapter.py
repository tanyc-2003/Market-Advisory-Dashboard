"""V7_lite point-in-time-safe FRED adapter.

FRED publishes economic data with revisions.  The **vintage API** lets
us ask "what was the published value of GS10 *as observed on
2024-06-15*?" — distinct from "what is the current revised value for
2024-06-15?".  V7_lite always uses the vintage path: every fetch issues
``realtime_start == realtime_end == observation_date`` so backtests
cannot accidentally see a later revision.

In V7 Institutional mode this strictness is optional because FRED is
not the sole macro source there — but we keep the helper available so
callers in either mode can opt into PIT-safety.
"""
from __future__ import annotations

import json
from datetime import date
from typing import Any
from urllib.parse import urlencode

import requests
import structlog

logger = structlog.get_logger(__name__)


FRED_OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"

# Series IDs routed through PIT-safe fetch in v7_lite mode.
LITE_FRED_SERIES: dict[str, str] = {
    "GS10":             "10-year Treasury yield",
    "T10Y2Y":           "10Y - 2Y yield curve spread",
    "BAMLH0A0HYM2OAS":  "ICE BofA HY OAS",
    "BAMLC0A0CM":       "ICE BofA IG OAS",
    "VIXCLS":           "VIX (1M, FRED-published)",
}


class FREDError(RuntimeError):
    """Raised when the FRED API returns a non-OK response."""


def fetch_fred_pit_safe(
    series_id: str,
    observation_date: date,
    api_key: str,
    timeout: float = 15.0,
    http_client: Any | None = None,
) -> float:
    """Return the value of ``series_id`` *as it was published on*
    ``observation_date``.  Returns ``float('nan')`` if the date is
    missing or marked ``"."`` by FRED.

    Parameters
    ----------
    http_client:
        Optional object exposing ``.get(url, timeout=...)`` — passed for
        tests to mock the network.
    """
    if not api_key:
        raise FREDError(
            "FRED API key not configured. Set FRED_API_KEY in .env or pass "
            "api_key= explicitly."
        )
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "observation_start": observation_date.isoformat(),
        "observation_end": observation_date.isoformat(),
        "realtime_start": observation_date.isoformat(),
        "realtime_end": observation_date.isoformat(),
    }
    url = f"{FRED_OBSERVATIONS_URL}?{urlencode(params)}"
    client = http_client or requests
    try:
        resp = client.get(url, timeout=timeout)
    except Exception as exc:  # pragma: no cover - network path
        logger.warning("fred_pit_fetch_failed", series_id=series_id, error=str(exc))
        return float("nan")

    if hasattr(resp, "status_code") and resp.status_code != 200:
        logger.warning(
            "fred_pit_non_ok",
            series_id=series_id,
            status=resp.status_code,
            body=getattr(resp, "text", "")[:200],
        )
        return float("nan")

    body = resp.json() if hasattr(resp, "json") else json.loads(resp.text)
    observations = body.get("observations") or []
    if not observations:
        return float("nan")
    raw_value = observations[0].get("value", ".")
    if raw_value in ("", ".", None):
        return float("nan")
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return float("nan")


def fetch_fred_series(
    series_id: str,
    start: date,
    end: date,
    api_key: str,
    app_mode: str = "v7_lite",
    http_client: Any | None = None,
) -> list[tuple[date, float]]:
    """Public interface for FRED data fetches.

    In ``v7_lite`` mode every observation date is fetched through
    :func:`fetch_fred_pit_safe` (one HTTP request per date).  In
    ``v7_institutional`` mode the caller may use the cheaper bulk
    endpoint — that path is left as a follow-up (returns the same shape
    via the PIT path for now).
    """
    if app_mode != "v7_lite":
        # V7 Institutional path — for now we just call the PIT path
        # because the FRED bulk endpoint is functionally identical when
        # realtime_start/end are omitted.  Sharadar is the canonical
        # institutional macro source; FRED is a cross-check there.
        pass

    out: list[tuple[date, float]] = []
    cursor = start
    while cursor <= end:
        if cursor.weekday() < 5:
            value = fetch_fred_pit_safe(
                series_id,
                cursor,
                api_key=api_key,
                http_client=http_client,
            )
            out.append((cursor, value))
        cursor = cursor.fromordinal(cursor.toordinal() + 1)
    return out
