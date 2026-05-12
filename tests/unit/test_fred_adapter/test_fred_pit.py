"""V7_lite Phase 2: FRED PIT-safe adapter (no network)."""
from __future__ import annotations

import json
import math
from datetime import date
from unittest.mock import MagicMock

import pytest

from src.advisory.data_infra.fred_adapter import (
    FREDError,
    fetch_fred_pit_safe,
)


class _Resp:
    def __init__(self, body: dict, status: int = 200):
        self._body = body
        self.status_code = status
        self.text = json.dumps(body)

    def json(self):
        return self._body


def test_pit_safe_passes_vintage_params():
    captured: dict = {}

    def fake_get(url, timeout=None):
        captured["url"] = url
        return _Resp({"observations": [{"value": "3.95"}]})

    client = MagicMock(get=fake_get)
    out = fetch_fred_pit_safe(
        "GS10", date(2024, 1, 2), api_key="KEY", http_client=client
    )
    assert out == 3.95
    assert "realtime_start=2024-01-02" in captured["url"]
    assert "realtime_end=2024-01-02" in captured["url"]
    assert "observation_start=2024-01-02" in captured["url"]


def test_returns_nan_for_dot_value():
    client = MagicMock(get=lambda u, timeout=None: _Resp({"observations": [{"value": "."}]}))
    out = fetch_fred_pit_safe("GS10", date(2024, 1, 2), api_key="K", http_client=client)
    assert math.isnan(out)


def test_returns_nan_for_empty_observations():
    client = MagicMock(get=lambda u, timeout=None: _Resp({"observations": []}))
    out = fetch_fred_pit_safe("GS10", date(2024, 1, 2), api_key="K", http_client=client)
    assert math.isnan(out)


def test_returns_nan_on_non_ok_status():
    client = MagicMock(
        get=lambda u, timeout=None: _Resp({"error": "rate limited"}, status=429)
    )
    out = fetch_fred_pit_safe("GS10", date(2024, 1, 2), api_key="K", http_client=client)
    assert math.isnan(out)


def test_raises_without_api_key():
    with pytest.raises(FREDError):
        fetch_fred_pit_safe("GS10", date(2024, 1, 2), api_key="")
