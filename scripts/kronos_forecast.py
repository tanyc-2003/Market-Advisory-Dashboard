#!/usr/bin/env python3
"""Refresh the Kronos transformer forecast cache (heavy — run out-of-band).

The transformer is too slow for the request path, so its per-ticker forecasts are
precomputed here into ``kronos_forecast_cache`` and the dashboard reads that. No-op
unless a *transformer* model is promoted.

    python scripts/kronos_forecast.py                # PIT archive + live-edge bar
    python scripts/kronos_forecast.py --no-live-edge # PIT archive only (reproducible)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import duckdb  # noqa: E402

from config.settings import settings  # noqa: E402
from src.advisory.api import kronos_forecast_live  # noqa: E402
from src.advisory.data_infra.schema import bootstrap_schema  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Refresh the Kronos forecast cache")
    ap.add_argument("--no-live-edge", action="store_true",
                    help="Do not append the current (un-ingested) yfinance bar")
    args = ap.parse_args()

    conn = duckdb.connect(str(settings.main_db_path))
    bootstrap_schema(conn)
    written = kronos_forecast_live.refresh_cache(conn, use_live_edge=not args.no_live_edge)
    if written == 0:
        print("Nothing cached — no promoted transformer model, or no px_* OHLCV archive.")
    else:
        print(f"Cached Kronos forecasts for {written} ticker(s).")
    conn.close()


if __name__ == "__main__":
    main()
