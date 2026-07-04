"""Dynamic-watchlist table logic + connection-based feature ingest.

Covers the pieces the in-app "add any ticker" flow relies on, without hitting
the network (yfinance): symbol validation, the lazy-seeded ``watchlist`` table,
add/status/remove, and writing features through a shared connection.
"""
from __future__ import annotations

from datetime import date, timedelta

import duckdb
import polars as pl
import pytest

from src.advisory.api import watchlist_live as wl
from src.advisory.data_infra.ingest import write_equity_ohlcv_conn, write_features_conn
from src.advisory.data_infra.schema import bootstrap_schema


@pytest.fixture
def conn():
    c = duckdb.connect(":memory:")
    bootstrap_schema(c)
    yield c
    c.close()


def test_valid_ticker():
    assert wl.valid_ticker("NVDA")
    assert wl.valid_ticker("BRK.B")
    assert wl.valid_ticker("RDS-A")
    assert not wl.valid_ticker("nvda")  # must be uppercase
    assert not wl.valid_ticker("$SPX")
    assert not wl.valid_ticker("")
    assert not wl.valid_ticker("TOOLONGTICKER")


def test_list_entries_lazy_seeds_defaults(conn):
    entries = wl.list_entries(conn)
    assert [e["ticker"] for e in entries] == [t for t, _ in wl._defaults()]
    assert all(e["status"] == "ready" for e in entries)


def test_add_keeps_defaults_and_marks_pending(conn):
    wl.list_entries(conn)  # seed defaults first
    wl.add(conn, "TSLA", "Auto")
    entries = {e["ticker"]: e for e in wl.list_entries(conn)}
    assert "NVDA" in entries  # defaults are not wiped by the first add
    assert entries["TSLA"]["status"] == "pending"


def test_add_on_empty_table_still_seeds_defaults(conn):
    # Regression: the very first watchlist operation is an add (no prior
    # list_entries). Defaults must still be seeded, not silently dropped.
    wl.add(conn, "TSLA", "Auto")
    tickers = [e["ticker"] for e in wl.list_entries(conn)]
    assert "NVDA" in tickers and "TSLA" in tickers


def test_set_status_and_remove(conn):
    wl.list_entries(conn)
    wl.add(conn, "TSLA")
    wl.set_status(conn, "TSLA", "ready")
    statuses = {e["ticker"]: e["status"] for e in wl.list_entries(conn)}
    assert statuses["TSLA"] == "ready"
    assert wl.remove(conn, "TSLA") is True
    assert wl.remove(conn, "ZZZZ") is False
    assert "TSLA" not in [e["ticker"] for e in wl.list_entries(conn)]


def test_add_rearms_existing_to_pending(conn):
    wl.list_entries(conn)
    wl.add(conn, "NVDA")  # already a default (ready) -> back to pending
    statuses = {e["ticker"]: e["status"] for e in wl.list_entries(conn)}
    assert statuses["NVDA"] == "pending"


def test_write_features_conn_roundtrip(conn):
    df = pl.DataFrame(
        {
            "ticker": ["ABC", "ABC"],
            "effective_date": [date(2024, 1, 2), date(2024, 1, 3)],
            "knowledge_date": [date(2024, 1, 2), date(2024, 1, 3)],
            "feature_name": ["ret_1d", "ret_1d"],
            "feature_value": [0.01, -0.02],
        }
    )
    assert write_features_conn(conn, df, source="test", version="v1") == 2
    assert conn.execute("SELECT count(*) FROM features_pit WHERE ticker='ABC'").fetchone()[0] == 2


def test_write_features_conn_rejects_missing_columns(conn):
    df = pl.DataFrame({"ticker": ["ABC"], "feature_value": [0.1]})
    with pytest.raises(ValueError):
        write_features_conn(conn, df, source="test", version="v1")


def _synth_ohlcv(ticker: str, n: int = 70) -> pl.DataFrame:
    days: list[date] = []
    cur = date(2024, 1, 1)
    while len(days) < n:
        if cur.weekday() < 5:
            days.append(cur)
        cur += timedelta(days=1)
    closes = [100.0 + i for i in range(n)]
    return pl.DataFrame(
        {
            "ticker": [ticker] * n,
            "effective_date": days,
            "open": closes,
            "high": [c + 1 for c in closes],
            "low": [c - 1 for c in closes],
            "close": closes,
            "volume": [1_000_000] * n,
        }
    )


def test_write_equity_ohlcv_conn_writes_features_and_px(conn):
    ohlcv = _synth_ohlcv("ABC")
    assert write_equity_ohlcv_conn(conn, ohlcv, "ABC") > 0
    feats = conn.execute(
        "SELECT count(*) FROM features_pit WHERE ticker='ABC' AND feature_name='ret_1d'"
    ).fetchone()[0]
    px = conn.execute(
        "SELECT count(*) FROM features_pit WHERE ticker='ABC' AND feature_name='px_close'"
    ).fetchone()[0]
    assert feats > 0
    assert px == 70
    # idempotent: a re-add refreshes rather than duplicating the ticker's rows.
    write_equity_ohlcv_conn(conn, ohlcv, "ABC")
    px2 = conn.execute(
        "SELECT count(*) FROM features_pit WHERE ticker='ABC' AND feature_name='px_close'"
    ).fetchone()[0]
    assert px2 == 70


def test_empty_ohlcv_writes_nothing(conn):
    empty = pl.DataFrame({"ticker": [], "effective_date": [], "close": []})
    assert write_equity_ohlcv_conn(conn, empty, "ABC") == 0
