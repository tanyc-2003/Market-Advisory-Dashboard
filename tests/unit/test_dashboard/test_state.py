"""Tests for the dashboard state helpers (Phase 12).

Streamlit is mocked: every state-helper uses a lazy ``_session()``
indirection so we can plug in a plain dict for the tests.
"""
from __future__ import annotations

import sys
from datetime import date
from types import SimpleNamespace

import pytest

from src.advisory.dashboard import state as state_mod


@pytest.fixture
def fake_session(monkeypatch):
    bucket: dict = {}
    monkeypatch.setattr(state_mod, "_session", lambda: bucket)
    # Also stub `streamlit` import in case anything in the chain
    # accidentally pulls it in.
    sys.modules.setdefault("streamlit", SimpleNamespace(session_state=bucket))
    return bucket


def test_init_seeds_defaults(fake_session):
    state_mod.init_session_state()
    assert fake_session["selected_ticker"] is None
    assert fake_session["portfolio_weights"] == {}
    assert isinstance(fake_session["as_of_date"], date)


def test_selected_ticker_round_trip(fake_session):
    state_mod.init_session_state()
    state_mod.set_selected_ticker("AAPL")
    assert state_mod.get_selected_ticker() == "AAPL"


def test_portfolio_weights_round_trip(fake_session):
    state_mod.init_session_state()
    state_mod.set_portfolio_weights({"AAPL": 0.5, "MSFT": 0.5})
    assert state_mod.get_portfolio_weights() == {"AAPL": 0.5, "MSFT": 0.5}


def test_layer_report_helpers(fake_session):
    state_mod.init_session_state()
    state_mod.set_active_layer_report("layer1", object())
    bucket = state_mod.get_active_layer_reports()
    assert "layer1" in bucket


def test_init_is_idempotent(fake_session):
    state_mod.init_session_state()
    state_mod.set_selected_ticker("ZZZ")
    state_mod.init_session_state()
    # init must not blow away an existing value
    assert state_mod.get_selected_ticker() == "ZZZ"


def test_llm_enabled_syncs_from_settings(fake_session, monkeypatch):
    from config.settings import settings

    monkeypatch.setattr(settings, "llm_enabled", True)
    state_mod.init_session_state()
    assert state_mod.is_llm_enabled() is True
    monkeypatch.setattr(settings, "llm_enabled", False)
    state_mod.init_session_state()
    assert state_mod.is_llm_enabled() is False
