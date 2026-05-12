"""Tests for JournalEntry + JournalStore (Phase 9)."""
from __future__ import annotations

from datetime import date

import duckdb
import pytest

from src.advisory.data_infra.schema import bootstrap_schema
from src.advisory.layer8_journal.entry import JournalEntry, JournalEntryError
from src.advisory.layer8_journal.store import JournalStore


def _entry(**overrides) -> JournalEntry:
    defaults = dict(
        entry_id="T-1",
        ticker="AAPL",
        entry_date=date(2024, 5, 1),
        direction="long",
        thesis="Earnings surprise + analog hit rate > 60%",
        primary_catalyst="Q2 earnings",
        invalidation="Close below 180 for 3 days",
        expected_horizon=10,
        confidence_self=4,
        market_state_id=2,
        analog_hit_rate=0.62,
        analog_n=30,
    )
    defaults.update(overrides)
    return JournalEntry(**defaults)


@pytest.fixture
def store():
    conn = duckdb.connect(":memory:")
    bootstrap_schema(conn)
    return JournalStore(conn)


def test_save_and_retrieve_open_trade(store):
    entry = _entry()
    store.save(entry)
    opens = store.get_open_trades()
    assert len(opens) == 1
    assert opens[0].ticker == "AAPL"


def test_close_trade_moves_to_completed(store):
    entry = _entry()
    store.save(entry)
    store.close_trade(
        "T-1",
        exit_date=date(2024, 5, 15),
        pnl_pct=0.05,
        exit_reason="Target reached",
        thesis_validated=True,
    )
    assert store.get_open_trades() == []
    completed = store.get_completed_trades()
    assert len(completed) == 1
    assert completed[0].is_complete


def test_validate_rejects_blank_thesis():
    with pytest.raises(JournalEntryError):
        _entry(thesis="   ").validate()


def test_validate_rejects_out_of_range_confidence():
    with pytest.raises(JournalEntryError):
        _entry(confidence_self=6).validate()


def test_validate_rejects_invalid_direction():
    with pytest.raises(JournalEntryError):
        _entry(direction="maybe").validate()


def test_validate_rejects_non_positive_horizon():
    with pytest.raises(JournalEntryError):
        _entry(expected_horizon=0).validate()


def test_as_polars_returns_all_columns(store):
    store.save(_entry())
    df = store.as_polars()
    expected = {
        "entry_id", "ticker", "entry_date", "direction", "thesis",
        "primary_catalyst", "invalidation", "expected_horizon",
        "confidence_self", "market_state_id", "analog_hit_rate", "analog_n",
        "contradictions", "unknowns_present", "exit_date", "pnl_pct",
        "thesis_validated", "exit_reason",
    }
    assert expected.issubset(set(df.columns))
