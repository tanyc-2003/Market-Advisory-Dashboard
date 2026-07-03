#!/usr/bin/env python3
"""Log / backfill / resolve system predictions for the self-grading track record.

    python scripts/track_record.py --log                       # log today's calls
    python scripts/track_record.py --backfill-days 500 --every 5   # seed history
    python scripts/track_record.py --resolve-only              # just resolve due ones

Predictions are point-in-time: each is computed from data on/before its
knowledge_date, then resolved against the realised forward return once the
horizon has elapsed. Idempotent per (ticker, knowledge_date).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import duckdb  # noqa: E402

from config.settings import settings  # noqa: E402
from src.advisory.api import analogs_live, track_record_live  # noqa: E402
from src.advisory.data_infra.schema import bootstrap_schema  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Manage system-prediction track record")
    ap.add_argument("--backfill-days", type=int, default=0,
                    help="Backfill predictions over this many trailing trading days")
    ap.add_argument("--every", type=int, default=5,
                    help="When backfilling, sample every Nth trading day (default weekly)")
    ap.add_argument("--log", action="store_true", help="Log predictions for the latest date")
    ap.add_argument("--resolve-only", action="store_true", help="Only resolve due predictions")
    args = ap.parse_args()

    conn = duckdb.connect(str(settings.main_db_path))
    bootstrap_schema(conn)
    tickers = [t for t, _ in analogs_live._WATCHLIST]

    dates = [r[0] for r in conn.execute(
        "SELECT DISTINCT effective_date FROM features_pit ORDER BY effective_date"
    ).fetchall()]
    if not dates:
        raise SystemExit("No features present. Run scripts/ingest_real_data.py first.")

    emitted = 0
    if not args.resolve_only and args.backfill_days > 0:
        horizon = track_record_live.HORIZON_DAYS
        usable = dates[:-(horizon + 1)] if len(dates) > horizon + 1 else []
        window = usable[-args.backfill_days:] if args.backfill_days < len(usable) else usable
        sample = window[:: max(1, args.every)]
        for d in sample:
            for tk in tickers:
                try:
                    if track_record_live.emit_prediction(conn, tk, as_of=d):
                        emitted += 1
                except Exception:
                    pass
        print(f"Backfilled {emitted} predictions across {len(sample)} dates")

    if not args.resolve_only and args.log:
        d = dates[-1]
        for tk in tickers:
            try:
                if track_record_live.emit_prediction(conn, tk, as_of=d):
                    emitted += 1
            except Exception:
                pass
        print(f"Logged predictions for {d}")

    resolved = track_record_live.resolve(conn)
    total = conn.execute("SELECT count(*) FROM system_predictions").fetchone()[0]
    done = conn.execute("SELECT count(*) FROM system_predictions WHERE resolved").fetchone()[0]
    print(f"Resolved {resolved} this run. Predictions: {total} total, {done} resolved.")
    conn.close()


if __name__ == "__main__":
    main()
