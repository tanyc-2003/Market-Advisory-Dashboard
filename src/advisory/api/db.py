"""Shared DuckDB connection management for the API.

The API runs as a single uvicorn process whose sync endpoints execute in a
threadpool, so DB access is serialised through one reentrant lock and one
shared read-write connection rather than opening the file per request (which
DuckDB rejects while another connection holds it).
"""
from __future__ import annotations

import threading

import duckdb

from config.settings import settings
from src.advisory.data_infra.schema import bootstrap_schema

#: Reentrant — held for the whole DB section of a request; ``get_main_conn``
#: re-acquires it internally without deadlocking.
LOCK = threading.RLock()

_main_conn: duckdb.DuckDBPyConnection | None = None


def main_db_exists() -> bool:
    return settings.main_db_path.exists()


def audit_db_exists() -> bool:
    return settings.audit_db_path.exists()


def get_main_conn(create: bool = False) -> duckdb.DuckDBPyConnection | None:
    """Return the shared connection to the main DB.

    When the file is absent and ``create`` is False, returns ``None`` so callers
    fall back to representative data. When ``create`` is True (the journal write
    path), the directory and schema are bootstrapped so journaling works even on
    a machine that never ran ``seed_synthetic_data.py``.
    """
    global _main_conn
    with LOCK:
        if _main_conn is not None:
            return _main_conn
        if not settings.main_db_path.exists() and not create:
            return None
        settings.main_db_path.parent.mkdir(parents=True, exist_ok=True)
        _main_conn = duckdb.connect(str(settings.main_db_path))
        bootstrap_schema(_main_conn)  # idempotent: CREATE TABLE IF NOT EXISTS
        return _main_conn
