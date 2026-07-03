#!/usr/bin/env python3
"""Record material recommendation changes into the decision change-log.

Run on a schedule (e.g. daily) or on demand. Compares the current per-ticker
recommendation (verdict / sizing band / disagreement) to the last recorded
state and appends a hashed row per changed field.

    python scripts/snapshot_recommendations.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import duckdb  # noqa: E402

from config.settings import settings  # noqa: E402
from src.advisory.api import recommendation_log  # noqa: E402
from src.advisory.data_infra.schema import bootstrap_schema  # noqa: E402


def main() -> None:
    conn = duckdb.connect(str(settings.main_db_path))
    bootstrap_schema(conn)
    recorded = recommendation_log.snapshot(conn)
    total = conn.execute("SELECT count(*) FROM recommendation_changes").fetchone()[0]
    print(f"Recorded {recorded} change row(s). Change-log now holds {total} row(s).")
    conn.close()


if __name__ == "__main__":
    main()
