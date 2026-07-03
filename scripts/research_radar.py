#!/usr/bin/env python3
"""Refresh the arXiv research-radar cache (network fetch).

Run daily / on demand. The dashboard reads the cache only; this is the only
step that touches the network.

    python scripts/research_radar.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import duckdb  # noqa: E402

from config.settings import settings  # noqa: E402
from src.advisory.api import research_radar_live  # noqa: E402
from src.advisory.data_infra.schema import bootstrap_schema  # noqa: E402


def main() -> None:
    conn = duckdb.connect(str(settings.main_db_path))
    bootstrap_schema(conn)
    written = research_radar_live.refresh(conn)
    total = conn.execute("SELECT count(*) FROM research_cache").fetchone()[0]
    print(f"Fetched/updated {written} paper(s). Cache now holds {total} entr(ies).")
    conn.close()


if __name__ == "__main__":
    main()
