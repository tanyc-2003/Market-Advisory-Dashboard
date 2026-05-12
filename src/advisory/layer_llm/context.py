"""Context packet sent to the LLM.

Architectural caps:

* ``MAX_TOKENS`` (estimated, ~2,000): the packet is shrunk until it
  fits.  We shrink by reducing ``max_assets`` first, then alert count.
* ``MAX_MARKET_STATE_SENTENCES``: the prose summary of the market state
  is truncated to 3 sentences.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


MAX_TOKENS: int = 2000
MAX_MARKET_STATE_SENTENCES: int = 3
DEFAULT_MAX_ASSETS: int = 15
TOKEN_PER_WORD: float = 1.3


def estimate_tokens(text: str) -> int:
    """Cheap token-count proxy used to enforce the 2,000-token cap."""
    return int(len(text.split()) * TOKEN_PER_WORD)


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _truncate_sentences(text: str, max_sentences: int) -> str:
    parts = _SENTENCE_SPLIT.split(text.strip())
    if len(parts) <= max_sentences:
        return text.strip()
    return " ".join(parts[:max_sentences])


@dataclass
class LLMContextPacket:
    """Pre-filtered context sent to the LLM (<=~2,000 tokens)."""

    date: str
    market_state: str  # max MAX_MARKET_STATE_SENTENCES sentences
    top_decile: list[dict[str, Any]] = field(default_factory=list)
    alerts: list[dict[str, Any]] = field(default_factory=list)
    calibration_note: str = ""
    unknowns: list[str] = field(default_factory=list)
    analyst_query: str = ""

    def estimated_tokens(self) -> int:
        body = (
            f"{self.date}\n{self.market_state}\n"
            f"{self.top_decile}\n{self.alerts}\n"
            f"{self.calibration_note}\n{self.unknowns}\n{self.analyst_query}"
        )
        return estimate_tokens(body)


def _summarise_market_state(market_state: dict[str, Any]) -> str:
    summary = (
        market_state.get("summary")
        or market_state.get("market_state")
        or "Market state summary not available."
    )
    return _truncate_sentences(str(summary), MAX_MARKET_STATE_SENTENCES)


def _select_top_assets(
    attribution_map: dict[str, dict[str, Any]], max_assets: int
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ticker, info in attribution_map.items():
        top = info.get("top_features", [])
        rows.append(
            {
                "ticker": ticker,
                "top_features": list(top)[:3],
                "background_vintage": info.get("background_vintage"),
                "tight_top_margin": bool(info.get("tight_top_margin", False)),
            }
        )
    return rows[:max_assets]


def _select_alerts(alerts: list[dict[str, Any]], k: int = 5) -> list[dict[str, Any]]:
    return list(alerts)[:k]


def build_context_packet(
    analyst_query: str,
    market_state: dict[str, Any],
    analog_result: dict[str, Any],
    attribution_map: dict[str, dict[str, Any]],
    alerts: list[dict[str, Any]],
    calibration: dict[str, Any],
    unknowns: list[str],
    max_assets: int = DEFAULT_MAX_ASSETS,
    as_of: str | None = None,
) -> LLMContextPacket:
    """Build a packet, shrinking it until it fits the ~2,000-token cap."""
    if not analyst_query or not analyst_query.strip():
        raise ValueError("analyst_query must be non-empty")

    date_str = as_of or market_state.get("as_of") or "today"
    summary = _summarise_market_state(market_state)
    calibration_note = (
        calibration.get("calibration_band")
        and f"Trader calibration: {calibration['calibration_band']}."
    ) or (calibration.get("note") or "Calibration not yet evaluated.")

    # Iteratively shrink until under MAX_TOKENS.
    n_assets = max_assets
    n_alerts = 5
    while True:
        packet = LLMContextPacket(
            date=str(date_str),
            market_state=summary,
            top_decile=_select_top_assets(attribution_map, n_assets),
            alerts=_select_alerts(alerts, n_alerts),
            calibration_note=str(calibration_note),
            unknowns=list(unknowns)[:6],
            analyst_query=analyst_query.strip(),
        )
        if packet.estimated_tokens() <= MAX_TOKENS:
            break
        if n_assets > 3:
            n_assets -= 1
            continue
        if n_alerts > 1:
            n_alerts -= 1
            continue
        # Cap not reachable purely by trimming lists — accept the packet
        # but warn loudly.
        logger.warning(
            "llm_context_oversize",
            tokens=packet.estimated_tokens(),
            cap=MAX_TOKENS,
        )
        break

    logger.debug(
        "llm_context_built",
        n_assets=len(packet.top_decile),
        n_alerts=len(packet.alerts),
        tokens=packet.estimated_tokens(),
    )
    return packet
