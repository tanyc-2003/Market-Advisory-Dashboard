"""Tier 3 #8 — arXiv research radar.

Auto-pulls recent arXiv papers matching the methods this system uses. The
network fetch (``refresh``) is explicit — run by ``scripts/research_radar.py`` /
a scheduler — so the GET path only reads the ``research_cache`` table and never
blocks on the network. Degrades to whatever is cached (or empty).
"""
from __future__ import annotations

from typing import Any

import duckdb

# topic label -> full arXiv search_query (phrase/category scoped for relevance)
_TOPICS = {
    "regime detection": 'all:"market regime" AND all:"hidden markov"',
    "deflated sharpe": 'all:"deflated sharpe"',
    "position sizing": 'all:"kelly criterion" AND cat:q-fin.*',
    "calibration": 'all:"forecast calibration" OR all:"reliability diagram"',
    "market analogs": 'all:"analog" AND cat:q-fin.*',
}

_PER_TOPIC = 4
_LIMIT = 24
_ATOM = "{http://www.w3.org/2005/Atom}"


def refresh(conn: duckdb.DuckDBPyConnection, per_topic: int = _PER_TOPIC) -> int:
    """Fetch each topic from arXiv and upsert into research_cache. Returns rows written."""
    import xml.etree.ElementTree as ET
    from datetime import date

    import requests

    written = 0
    for topic, terms in _TOPICS.items():
        try:
            resp = requests.get(
                "http://export.arxiv.org/api/query",
                params={
                    "search_query": terms,
                    "max_results": per_topic,
                    "sortBy": "submittedDate",
                    "sortOrder": "descending",
                },
                timeout=15,
            )
            resp.raise_for_status()
            root = ET.fromstring(resp.text)
        except Exception:
            continue  # skip this topic; never fail the refresh

        for entry in root.findall(f"{_ATOM}entry"):
            eid = (entry.findtext(f"{_ATOM}id") or "").strip()
            if not eid:
                continue
            title = " ".join((entry.findtext(f"{_ATOM}title") or "").split())
            summary = " ".join((entry.findtext(f"{_ATOM}summary") or "").split())
            authors = ", ".join(
                (a.findtext(f"{_ATOM}name") or "").strip()
                for a in entry.findall(f"{_ATOM}author")
            )
            published_raw = (entry.findtext(f"{_ATOM}published") or "")[:10]
            try:
                published = date.fromisoformat(published_raw)
            except ValueError:
                published = None
            url = eid
            for link in entry.findall(f"{_ATOM}link"):
                if link.get("rel") == "alternate":
                    url = link.get("href", eid)
            conn.execute(
                "INSERT INTO research_cache (entry_id, topic, title, authors, published, url, summary, fetched_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, now()) "
                "ON CONFLICT (entry_id) DO UPDATE SET fetched_at = now(), topic = excluded.topic",
                [eid, topic, title[:500], authors[:500], published, url, summary[:2000]],
            )
            written += 1
    return written


def compute_research_radar(conn: duckdb.DuckDBPyConnection | None) -> dict[str, Any] | None:
    """Read cached papers only (no network). None if the cache is empty."""
    if conn is None:
        return None
    try:
        rows = conn.execute(
            "SELECT topic, title, authors, published, url, summary, fetched_at "
            "FROM research_cache ORDER BY published DESC NULLS LAST LIMIT ?",
            [_LIMIT],
        ).fetchall()
        fetched = conn.execute("SELECT max(fetched_at) FROM research_cache").fetchone()
    except Exception:
        return None
    if not rows:
        return None
    items = [
        {
            "topic": r[0], "title": r[1], "authors": r[2],
            "published": str(r[3]) if r[3] is not None else None,
            "url": r[4], "summary": r[5],
        }
        for r in rows
    ]
    return {"fetchedAt": str(fetched[0]) if fetched and fetched[0] else None, "items": items, "source": "live"}
