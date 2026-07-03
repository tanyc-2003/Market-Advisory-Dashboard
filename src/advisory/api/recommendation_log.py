"""Tier 2 #5 — decision change-log ("trading-as-git").

Records *material* changes to each ticker's recommendation (verdict, sizing
band, regime disagreement) as an append-only, hashed chain, with an optional
operator rationale (the "commit message"). Snapshotting is explicit
(`scripts/snapshot_recommendations.py`), never on the GET path; the dashboard
only reads recent changes.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

import duckdb

from config.settings import settings

from . import analogs_live, market_state_live, synthesis_live

_FIELDS = ("verdict", "sizing_band", "disagreement")
_VERDICTS = ("lean long", "neutral", "lean short")
_LIMIT = 60


def _hash(ticker: str, state: dict[str, str]) -> str:
    payload = ticker + "|" + json.dumps({f: state.get(f) for f in _FIELDS}, sort_keys=True)
    return hashlib.sha1(payload.encode()).hexdigest()


def _current_states(conn: duckdb.DuckDBPyConnection) -> dict[str, dict[str, Any]]:
    assets = analogs_live.compute_watchlist(conn)
    if not assets:
        return {}
    ms = market_state_live.compute_market_state(conn) or {"states": []}
    synthesis_live.build_cases(assets, ms)
    out: dict[str, dict[str, Any]] = {}
    for a in assets:
        displayed = float(a.get("sizing", {}).get("displayed", 0.0))
        out[a["ticker"]] = {
            "verdict": a["case"]["verdict"],
            "sizing_band": f"{round(displayed / 0.05) * 0.05:.2f}",
            "disagreement": "yes" if a.get("disagreement") else "no",
            "_displayed": displayed,
        }
    return out


def snapshot(conn: duckdb.DuckDBPyConnection) -> int:
    """Record material changes vs. the last snapshot. Returns rows written."""
    states = _current_states(conn)
    recorded = 0
    for ticker, st in states.items():
        prev: dict[str, str] = {}
        for field in _FIELDS:
            row = conn.execute(
                "SELECT new_value FROM recommendation_changes WHERE ticker = ? AND field = ? "
                "ORDER BY changed_at DESC LIMIT 1",
                [ticker, field],
            ).fetchone()
            if row and row[0] is not None:
                prev[field] = row[0]

        new_hash = _hash(ticker, st)
        prev_hash = _hash(ticker, prev) if prev else None
        guard_passed = st["verdict"] in _VERDICTS and st["_displayed"] <= settings.kelly_absolute_cap + 1e-9

        for field in _FIELDS:
            if prev.get(field) != st[field]:
                conn.execute(
                    "INSERT INTO recommendation_changes "
                    "(change_id, ticker, field, prev_value, new_value, prev_hash, new_hash, guard_passed) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    [uuid.uuid4().hex, ticker, field, prev.get(field), st[field], prev_hash, new_hash, guard_passed],
                )
                recorded += 1
    return recorded


def attach_rationale(conn: duckdb.DuckDBPyConnection, ticker: str, rationale: str) -> bool:
    """Attach an operator rationale to the ticker's most recent change event."""
    latest = conn.execute(
        "SELECT new_hash FROM recommendation_changes WHERE ticker = ? ORDER BY changed_at DESC LIMIT 1",
        [ticker],
    ).fetchone()
    if not latest:
        return False
    conn.execute(
        "UPDATE recommendation_changes SET rationale = ? WHERE ticker = ? AND new_hash = ?",
        [rationale.strip(), ticker, latest[0]],
    )
    return True


def compute_recommendation_changes(conn: duckdb.DuckDBPyConnection | None) -> dict[str, Any] | None:
    if conn is None:
        return None
    try:
        rows = conn.execute(
            "SELECT change_id, ticker, changed_at, field, prev_value, new_value, rationale, guard_passed "
            "FROM recommendation_changes ORDER BY changed_at DESC LIMIT ?",
            [_LIMIT],
        ).fetchall()
    except Exception:
        return None
    if not rows:
        return None
    items = [
        {
            "id": r[0], "ticker": r[1], "changedAt": str(r[2]), "field": r[3],
            "prev": r[4], "new": r[5], "rationale": r[6], "guardPassed": bool(r[7]),
        }
        for r in rows
    ]
    return {"items": items, "source": "live"}
