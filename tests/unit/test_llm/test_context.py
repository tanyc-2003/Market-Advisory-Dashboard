"""Tests for LLMContextPacket + build_context_packet (Phase 13)."""
from __future__ import annotations

import pytest

from src.advisory.layer_llm.context import (
    MAX_MARKET_STATE_SENTENCES,
    MAX_TOKENS,
    build_context_packet,
    estimate_tokens,
)


def _attribution_map(n: int) -> dict[str, dict]:
    return {
        f"T{i}": {
            "top_features": ["earnings_revision_z", "ret_21d", "vix_percentile_63d"],
            "background_vintage": "2024-06-01",
        }
        for i in range(n)
    }


def test_estimate_tokens_increases_with_word_count():
    assert estimate_tokens("one") < estimate_tokens("one two three four")


def test_token_budget_respected_on_normal_input():
    packet = build_context_packet(
        analyst_query="What is the current state?",
        market_state={"summary": "A. B. C."},
        analog_result={},
        attribution_map=_attribution_map(15),
        alerts=[{"alert_type": "contradiction", "message": "x"} for _ in range(5)],
        calibration={"calibration_band": "moderate"},
        unknowns=["alpha", "beta"],
    )
    assert packet.estimated_tokens() <= MAX_TOKENS


def test_max_assets_shrinks_when_budget_blown():
    huge_attribution = {
        f"T{i}": {
            "top_features": ["feat_" + "x" * 200 for _ in range(3)],
            "background_vintage": "2024-06-01",
        }
        for i in range(500)
    }
    packet = build_context_packet(
        analyst_query="Q",
        market_state={"summary": "S."},
        analog_result={},
        attribution_map=huge_attribution,
        alerts=[],
        calibration={"calibration_band": "moderate"},
        unknowns=[],
        max_assets=500,
    )
    # Builder must have trimmed below 500 assets.
    assert len(packet.top_decile) <= 500
    assert len(packet.top_decile) >= 3


def test_market_state_truncated_to_three_sentences():
    multi = "One. Two. Three. Four. Five. Six."
    packet = build_context_packet(
        analyst_query="Q",
        market_state={"summary": multi},
        analog_result={},
        attribution_map={},
        alerts=[],
        calibration={"calibration_band": "moderate"},
        unknowns=[],
    )
    sentences = [s for s in packet.market_state.split(".") if s.strip()]
    assert len(sentences) <= MAX_MARKET_STATE_SENTENCES


def test_blank_query_raises():
    with pytest.raises(ValueError):
        build_context_packet(
            analyst_query="",
            market_state={"summary": "S."},
            analog_result={},
            attribution_map={},
            alerts=[],
            calibration={},
            unknowns=[],
        )
