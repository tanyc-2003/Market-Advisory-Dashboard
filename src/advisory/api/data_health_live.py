"""Tier 1 #2 — data freshness & PIT health monitor.

Grades the *inputs* the way Layer 0 grades outputs: per feed, last date,
trading-days-behind, PIT lag. Reuses ``features_pit`` (dates/counts) and
``yfinance_fetch_audit`` (status/gaps) — no new tables.
"""
from __future__ import annotations

from typing import Any

import duckdb

_FRESH_MAX = 2   # trading days behind the dataset's latest date
_STALE_MAX = 5


def _classify(stale_days: int, rows: int) -> str:
    if rows == 0 or stale_days > _STALE_MAX:
        return "missing"
    if stale_days > _FRESH_MAX:
        return "stale"
    return "fresh"


def _worst(statuses: list[str]) -> str:
    order = {"fresh": 0, "stale": 1, "missing": 2, "unknown": 3}
    return max(statuses, key=lambda s: order.get(s, 0)) if statuses else "unknown"


def compute_data_health(conn: duckdb.DuckDBPyConnection | None) -> dict[str, Any] | None:
    if conn is None:
        return None
    try:
        row = conn.execute("SELECT max(effective_date) FROM features_pit").fetchone()
    except Exception:
        return None
    if not row or row[0] is None:
        return None
    max_date = row[0]

    all_dates = [r[0] for r in conn.execute(
        "SELECT DISTINCT effective_date FROM features_pit ORDER BY effective_date"
    ).fetchall()]
    date_index = {d: i for i, d in enumerate(all_dates)}
    last_i = len(all_dates) - 1

    # Latest audit row per ticker (best effort).
    audit: dict[str, tuple] = {}
    try:
        for tk, status, ngap in conn.execute(
            """
            SELECT ticker, status, n_consec_gaps FROM yfinance_fetch_audit qa
            WHERE fetched_at = (SELECT max(fetched_at) FROM yfinance_fetch_audit q2
                                WHERE q2.ticker = qa.ticker)
            """
        ).fetchall():
            audit[tk] = (status, ngap)
    except Exception:
        pass

    feeds: list[dict[str, Any]] = []

    for tk, lastd, lastk, cnt in conn.execute(
        "SELECT ticker, max(effective_date), max(knowledge_date), count(*) "
        "FROM features_pit WHERE source = 'yfinance' GROUP BY ticker ORDER BY ticker"
    ).fetchall():
        stale = last_i - date_index.get(lastd, last_i)
        st, ngap = audit.get(tk, (None, 0))
        feeds.append({
            "name": tk, "source": "yfinance", "lastDate": str(lastd),
            "staleDays": int(stale),
            "pitLagDays": int((lastk - lastd).days) if lastk and lastd else 0,
            "rows": int(cnt), "gaps": int(ngap or 0),
            "status": _classify(int(stale), int(cnt)),
        })

    for fn, lastd, cnt in conn.execute(
        "SELECT feature_name, max(effective_date), count(*) "
        "FROM features_pit WHERE source = 'fred' GROUP BY feature_name ORDER BY feature_name"
    ).fetchall():
        stale = last_i - date_index.get(lastd, last_i)
        feeds.append({
            "name": fn, "source": "fred", "lastDate": str(lastd),
            "staleDays": int(stale), "pitLagDays": 0, "rows": int(cnt), "gaps": 0,
            "status": _classify(int(stale), int(cnt)),
        })

    if not feeds:
        return None
    return {
        "asOf": f"{max_date:%b %d, %Y}",
        "overall": _worst([f["status"] for f in feeds]),
        "feeds": feeds,
        "source": "live",
    }
