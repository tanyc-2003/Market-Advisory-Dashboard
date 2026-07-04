"""Dynamic, user-editable watchlist backed by the ``watchlist`` table.

The set of tickers the dashboard computes analogs for is no longer hardcoded:
it is read from ``watchlist`` (lazy-seeded with the defaults). A ticker added
in-app is inserted ``pending`` and ingested **asynchronously** — the network
fetch runs off the DB lock, the write happens under it, and ``status`` walks
``pending -> ready`` (or ``-> error``). The Overview shows the pending row until
it flips, then the analog distribution fills in.
"""
from __future__ import annotations

import re
import threading
from datetime import date, timedelta
from typing import Any

import duckdb

from . import analogs_live, db

#: Uppercase symbol, 1–10 chars, allowing dots/hyphens (BRK.B, RDS-A).
_TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")
_LOOKBACK_DAYS = 3650  # ~10y, matching ingest_real_data's default window


def valid_ticker(ticker: str) -> bool:
    return bool(_TICKER_RE.match(ticker))


def _defaults() -> list[tuple[str, str]]:
    return list(analogs_live._WATCHLIST)


def _ensure_seeded(conn: duckdb.DuckDBPyConnection) -> None:
    """Seed the default names once, on a first-ever-empty table.

    Must run before any user add, otherwise adding a single ticker to an empty
    table would make the defaults never appear.
    """
    if conn.execute("SELECT 1 FROM watchlist LIMIT 1").fetchone():
        return
    for t, s in _defaults():
        conn.execute(
            "INSERT INTO watchlist (ticker, sector, status) VALUES (?, ?, 'ready') "
            "ON CONFLICT (ticker) DO NOTHING",
            [t, s],
        )


def list_entries(conn: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    """Return ``[{ticker, sector, status}]`` in insertion order (defaults seeded)."""
    _ensure_seeded(conn)
    rows = conn.execute("SELECT ticker, sector, status FROM watchlist ORDER BY added_at, ticker").fetchall()
    return [{"ticker": r[0], "sector": r[1] or "—", "status": r[2]} for r in rows]


def add(conn: duckdb.DuckDBPyConnection, ticker: str, sector: str = "—") -> None:
    """Insert (or re-arm) a ticker as ``pending`` (seeding defaults first)."""
    _ensure_seeded(conn)
    conn.execute(
        "INSERT INTO watchlist (ticker, sector, status) VALUES (?, ?, 'pending') "
        "ON CONFLICT (ticker) DO UPDATE SET status = 'pending'",
        [ticker, sector],
    )


def set_status(conn: duckdb.DuckDBPyConnection, ticker: str, status: str) -> None:
    conn.execute("UPDATE watchlist SET status = ? WHERE ticker = ?", [status, ticker])


def remove(conn: duckdb.DuckDBPyConnection, ticker: str) -> bool:
    if not conn.execute("SELECT 1 FROM watchlist WHERE ticker = ?", [ticker]).fetchone():
        return False
    conn.execute("DELETE FROM watchlist WHERE ticker = ?", [ticker])
    return True


def start_ingest(ticker: str) -> None:
    """Kick off the async ingest for ``ticker`` (fire-and-forget daemon thread)."""
    threading.Thread(target=_ingest_job, args=(ticker,), daemon=True).start()


def _ingest_job(ticker: str) -> None:
    """Fetch OHLCV off the lock, write features under it, then flip status."""
    from ..data_infra.ingest import write_equity_ohlcv_conn
    from ..data_infra.ingestion import YFinanceConnector

    end = date.today()
    start = end - timedelta(days=_LOOKBACK_DAYS)
    try:
        ohlcv = YFinanceConnector().fetch_daily_ohlcv([ticker], start, end)  # network — no DB lock held
    except Exception:
        ohlcv = None

    with db.LOCK:
        conn = db.get_main_conn(create=True)
        if conn is None:
            return
        try:
            if ohlcv is None or ohlcv.is_empty():
                set_status(conn, ticker, "error")
            else:
                write_equity_ohlcv_conn(conn, ohlcv, ticker)
                set_status(conn, ticker, "ready")
        except Exception:
            try:
                set_status(conn, ticker, "error")
            except Exception:
                pass
    analogs_live.invalidate_cache()
