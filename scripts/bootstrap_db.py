#!/usr/bin/env python3
"""Create both DuckDB files and apply all schema DDL.  Idempotent."""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb

# Make `config.settings` and `src.advisory` importable when run directly.
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from config.settings import settings  # noqa: E402
from src.advisory.data_infra.schema import bootstrap_schema  # noqa: E402
from src.advisory.layer0_validation.audit_log import AuditLog  # noqa: E402


def main() -> None:
    settings.main_db_path.parent.mkdir(parents=True, exist_ok=True)
    settings.audit_db_path.parent.mkdir(parents=True, exist_ok=True)
    settings.cache_dir.mkdir(parents=True, exist_ok=True)

    main_conn = duckdb.connect(str(settings.main_db_path))
    try:
        bootstrap_schema(main_conn)
        print(f"[OK] Main DB schema applied: {settings.main_db_path}")
    finally:
        main_conn.close()

    audit = AuditLog(settings.audit_db_path)
    try:
        print(f"[OK] Audit DB ready: {settings.audit_db_path}")
        print(f"     Current trial count: {audit.trial_count()}")
    finally:
        audit.close()


if __name__ == "__main__":
    main()
