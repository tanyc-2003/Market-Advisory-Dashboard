"""Session-state helpers.

All access to ``st.session_state`` flows through this module.  Pages do
not read or write the session dict directly — they call the typed
helpers below so the contract is centralised.

The helpers are written to be importable without Streamlit (so tests
can exercise them).  Streamlit is imported lazily inside each function.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Mapping

from config.settings import settings


# Snapshot of the default state keys.  Pages must not invent new keys
# without adding them here.
DEFAULT_STATE: dict[str, Any] = {
    "selected_ticker":      None,
    "portfolio_weights":    {},
    "journal_open_trades":  [],
    "as_of_date":           None,           # populated by init_session_state
    "llm_enabled":          False,          # mirrors settings.llm_enabled
    "active_layer_reports": {},             # {layer_name: ValidationReport}
    "last_market_state":    None,
    "last_analog_result":   None,
}


def _session() -> Any:
    """Return ``st.session_state``.  Streamlit imported lazily."""
    import streamlit as st

    return st.session_state


def init_session_state() -> None:
    """Idempotently seed defaults.  Safe to call on every page render."""
    s = _session()
    for key, default in DEFAULT_STATE.items():
        if key not in s:
            s[key] = default
    if s.get("as_of_date") is None:
        s["as_of_date"] = date.today()
    # Sync from environment-driven settings every call so flipping
    # `LLM_ENABLED=true` in .env reflects without a Python restart.
    s["llm_enabled"] = bool(settings.llm_enabled)


# --- typed accessors -------------------------------------------------------

def get_selected_ticker() -> str | None:
    return _session().get("selected_ticker")


def set_selected_ticker(ticker: str | None) -> None:
    _session()["selected_ticker"] = ticker


def get_portfolio_weights() -> dict[str, float]:
    return dict(_session().get("portfolio_weights", {}))


def set_portfolio_weights(weights: Mapping[str, float]) -> None:
    _session()["portfolio_weights"] = dict(weights)


def get_as_of_date() -> date:
    value = _session().get("as_of_date") or date.today()
    return value


def set_as_of_date(d: date) -> None:
    _session()["as_of_date"] = d


def get_active_layer_reports() -> dict[str, Any]:
    return dict(_session().get("active_layer_reports", {}))


def set_active_layer_report(layer_name: str, report: Any) -> None:
    s = _session()
    bucket = dict(s.get("active_layer_reports", {}))
    bucket[layer_name] = report
    s["active_layer_reports"] = bucket


def is_llm_enabled() -> bool:
    return bool(_session().get("llm_enabled", False))


def get_last_market_state() -> Any:
    return _session().get("last_market_state")


def set_last_market_state(value: Any) -> None:
    _session()["last_market_state"] = value


def get_last_analog_result() -> Any:
    return _session().get("last_analog_result")


def set_last_analog_result(value: Any) -> None:
    _session()["last_analog_result"] = value
