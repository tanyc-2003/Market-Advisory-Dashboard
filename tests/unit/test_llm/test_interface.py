"""Tests for CachedLLMInterface (Phase 13).

The real Ollama call is replaced by a stub ``invoker``; the test focuses
on caching, TTL, hash uniqueness, prompt construction, and graceful
degradation.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from src.advisory.layer_llm.context import LLMContextPacket
from src.advisory.layer_llm.interface import (
    CACHE_TTL_DAYS,
    SYSTEM_PROMPT,
    CachedLLMInterface,
    build_prompt,
    compute_prompt_hash,
)


@pytest.fixture
def packet() -> LLMContextPacket:
    return LLMContextPacket(
        date="2024-06-01",
        market_state="Calm bull.",
        top_decile=[{"ticker": "AAPL", "top_features": ["x"], "background_vintage": "2024-06-01"}],
        alerts=[],
        calibration_note="Moderately calibrated.",
        unknowns=["alpha"],
        analyst_query="What does this state suggest?",
    )


def test_system_prompt_lists_prohibitions():
    for phrase in [
        "Inferring causality",
        "Generating trading rules",
        "Recommending position sizes",
        "Promoting any signal",
        "Overriding or explaining away contradictions",
    ]:
        assert phrase in SYSTEM_PROMPT


def test_build_prompt_carries_query_and_unknowns(packet):
    prompt = build_prompt(packet)
    assert "ANALYST QUERY" in prompt
    assert packet.analyst_query in prompt
    assert "SYSTEM DOES NOT KNOW" in prompt
    assert "alpha" in prompt


def test_hash_is_stable_for_identical_inputs():
    h1 = compute_prompt_hash("m", date(2024, 6, 1), "P")
    h2 = compute_prompt_hash("m", date(2024, 6, 1), "P")
    assert h1 == h2


def test_hash_differs_across_dates():
    h1 = compute_prompt_hash("m", date(2024, 6, 1), "P")
    h2 = compute_prompt_hash("m", date(2024, 6, 2), "P")
    assert h1 != h2


def test_cache_hit_on_same_day_same_query(tmp_path: Path, packet):
    db = tmp_path / "cache.duckdb"
    calls: list[str] = []

    def stub(prompt: str) -> str:
        calls.append(prompt)
        return "RESPONSE-A"

    iface = CachedLLMInterface(db_path=db, invoker=stub)
    try:
        r1 = iface.query(packet, as_of_date=date(2024, 6, 1))
        r2 = iface.query(packet, as_of_date=date(2024, 6, 1))
    finally:
        iface.close()
    assert r1["cache_hit"] is False
    assert r2["cache_hit"] is True
    assert r1["response"] == r2["response"] == "RESPONSE-A"
    assert len(calls) == 1  # only the first call hit the LLM


def test_cache_miss_on_different_date(tmp_path: Path, packet):
    db = tmp_path / "cache.duckdb"
    counter = {"n": 0}

    def stub(prompt: str) -> str:
        counter["n"] += 1
        return f"R{counter['n']}"

    iface = CachedLLMInterface(db_path=db, invoker=stub)
    try:
        iface.query(packet, as_of_date=date(2024, 6, 1))
        r2 = iface.query(packet, as_of_date=date(2024, 6, 2))
    finally:
        iface.close()
    assert r2["cache_hit"] is False
    assert counter["n"] == 2


def test_stale_cache_rejected_after_ttl(tmp_path: Path, packet):
    db = tmp_path / "cache.duckdb"

    fake_now = {"value": datetime(2024, 6, 1, 12, 0, 0)}

    def stub(prompt: str) -> str:
        return "old"

    iface = CachedLLMInterface(
        db_path=db,
        invoker=stub,
        now=lambda: fake_now["value"],
    )
    try:
        iface.query(packet, as_of_date=date(2024, 6, 1))
        # Advance clock past TTL.
        fake_now["value"] = fake_now["value"] + timedelta(days=CACHE_TTL_DAYS + 1)
        # Second call should miss the cache and re-invoke.
        invoked: list[bool] = []

        def stub2(prompt: str) -> str:
            invoked.append(True)
            return "fresh"

        iface._invoker_factory = stub2  # type: ignore[attr-defined]
        r = iface.query(packet, as_of_date=date(2024, 6, 1))
    finally:
        iface.close()
    assert r["cache_hit"] is False
    assert invoked == [True]


def test_invoker_failure_returns_graceful_error(tmp_path: Path, packet):
    db = tmp_path / "cache.duckdb"

    def broken(prompt: str) -> str:
        raise ConnectionError("Ollama not reachable")

    iface = CachedLLMInterface(db_path=db, invoker=broken)
    try:
        r = iface.query(packet, as_of_date=date(2024, 6, 1))
    finally:
        iface.close()
    assert r["error"] is True
    assert r["cache_hit"] is False
    assert "unavailable" in r["response"].lower()


def test_cache_hit_flag_present_on_both_paths(tmp_path: Path, packet):
    iface = CachedLLMInterface(db_path=tmp_path / "c.duckdb", invoker=lambda p: "ok")
    try:
        r1 = iface.query(packet, as_of_date=date(2024, 6, 1))
        r2 = iface.query(packet, as_of_date=date(2024, 6, 1))
    finally:
        iface.close()
    assert "cache_hit" in r1
    assert "cache_hit" in r2
