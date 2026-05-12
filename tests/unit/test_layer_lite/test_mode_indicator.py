"""V7_lite Phase 11: dashboard mode indicator + dev mode detection."""
from __future__ import annotations

from src.advisory.dashboard.components.mode_indicator import (
    DEVELOPER_MODE_BLOCK,
    INSTITUTIONAL_MODE_BLOCK,
    LITE_MODE_BLOCK,
    mode_block_for,
)


def test_lite_block_mentions_yfinance_and_lock():
    assert "yfinance" in LITE_MODE_BLOCK
    assert "Survivorship" in LITE_MODE_BLOCK
    assert "Locked" in LITE_MODE_BLOCK


def test_institutional_block_mentions_polygon_sharadar():
    assert "Polygon" in INSTITUTIONAL_MODE_BLOCK
    assert "Sharadar" in INSTITUTIONAL_MODE_BLOCK


def test_developer_block_mentions_synthetic():
    assert "synthetic" in DEVELOPER_MODE_BLOCK.lower()
    assert "DEVELOPER" in DEVELOPER_MODE_BLOCK


def test_mode_block_routes_correctly():
    assert mode_block_for("v7_lite", developer_mode=False) == LITE_MODE_BLOCK
    assert (
        mode_block_for("v7_institutional", developer_mode=False)
        == INSTITUTIONAL_MODE_BLOCK
    )
    assert (
        mode_block_for("v7_institutional", developer_mode=True)
        == DEVELOPER_MODE_BLOCK
    )


def test_developer_mode_detected_from_settings(monkeypatch):
    """Verify settings.developer_mode flips correctly based on key presence."""
    from config.settings import settings

    monkeypatch.setattr(settings, "app_mode", "v7_institutional")
    monkeypatch.setattr(settings, "polygon_api_key", "")
    monkeypatch.setattr(settings, "sharadar_api_key", "")
    assert settings.developer_mode is True

    monkeypatch.setattr(settings, "polygon_api_key", "abc")
    monkeypatch.setattr(settings, "sharadar_api_key", "def")
    assert settings.developer_mode is False

    monkeypatch.setattr(settings, "app_mode", "v7_lite")
    # Lite mode is never "developer mode" — even with no keys.
    monkeypatch.setattr(settings, "polygon_api_key", "")
    assert settings.developer_mode is False
