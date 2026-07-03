"""Tier 2 #6 — persistent per-ticker notes / inbox.

A durable feed of system alerts, resolved-call outcomes, and the trader's own
notes, per-ticker-tagged. Supersedes the ephemeral representative alerts.
"""
from __future__ import annotations

import uuid
from typing import Any

import duckdb

VALID_KINDS = ("alert", "system", "user", "outcome")
_LIMIT = 100


def add_note(
    conn: duckdb.DuckDBPyConnection,
    *,
    body: str,
    ticker: str | None = None,
    kind: str = "user",
    source: str = "trader",
    dedupe_key: str | None = None,
) -> str:
    """Insert a note. If ``dedupe_key`` is given, a standing note with the same
    (ticker, source, body) is not duplicated. Returns the note id (existing or new)."""
    if kind not in VALID_KINDS:
        kind = "system"
    if dedupe_key is not None:
        existing = conn.execute(
            "SELECT note_id FROM notes WHERE source = ? AND body = ? "
            "AND ticker IS NOT DISTINCT FROM ? LIMIT 1",
            [source, body, ticker],
        ).fetchone()
        if existing:
            return existing[0]
    note_id = uuid.uuid4().hex
    conn.execute(
        "INSERT INTO notes (note_id, ticker, kind, source, body, read) "
        "VALUES (?, ?, ?, ?, ?, FALSE)",
        [note_id, ticker, kind, source, body.strip()],
    )
    return note_id


def mark_read(conn: duckdb.DuckDBPyConnection, note_id: str) -> bool:
    before = conn.execute("SELECT count(*) FROM notes WHERE note_id = ?", [note_id]).fetchone()[0]
    if not before:
        return False
    conn.execute("UPDATE notes SET read = TRUE WHERE note_id = ?", [note_id])
    return True


def compute_notes(conn: duckdb.DuckDBPyConnection | None) -> dict[str, Any] | None:
    if conn is None:
        return None
    try:
        rows = conn.execute(
            "SELECT note_id, ticker, created_at, kind, source, body, read "
            "FROM notes ORDER BY created_at DESC LIMIT ?",
            [_LIMIT],
        ).fetchall()
        unread = conn.execute("SELECT count(*) FROM notes WHERE read = FALSE").fetchone()[0]
    except Exception:
        return None
    items = [
        {
            "id": r[0], "ticker": r[1], "createdAt": str(r[2]),
            "kind": r[3], "source": r[4], "body": r[5], "read": bool(r[6]),
        }
        for r in rows
    ]
    return {"unread": int(unread), "items": items, "source": "live"}
