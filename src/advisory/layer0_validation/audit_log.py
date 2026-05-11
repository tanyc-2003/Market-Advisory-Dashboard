"""Append-only audit log + monotonic backtest counter.

This log is the single authoritative source for the ``n_trials`` argument
to :func:`deflated_sharpe`.  It must be append-only and crash-safe; the
counter is derived from the row count of ``backtest_executions`` rather
than a separate column, so a half-written insert cannot drift it.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb
import structlog

logger = structlog.get_logger(__name__)


class AuditLog:
    """Append-only execution log backed by DuckDB.

    Parameters
    ----------
    db_path:
        Path to the audit DuckDB file.  Pass ``Path(':memory:')`` or the
        string ``":memory:"`` for an in-memory log (tests only).
    """

    def __init__(self, db_path: Path | str):
        if isinstance(db_path, Path):
            db_str = str(db_path)
        else:
            db_str = db_path
        self.conn = duckdb.connect(db_str)
        self._bootstrap()

    def _bootstrap(self) -> None:
        self.conn.execute("CREATE SEQUENCE IF NOT EXISTS exec_id_seq START 1;")
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS backtest_executions (
                execution_id    BIGINT PRIMARY KEY DEFAULT nextval('exec_id_seq'),
                layer_name      VARCHAR  NOT NULL,
                function_name   VARCHAR  NOT NULL,
                executed_at     TIMESTAMP NOT NULL DEFAULT now(),
                git_sha         VARCHAR,
                hyperparameters JSON
            );
            """
        )

    def record(
        self,
        layer_name: str,
        function_name: str,
        hyperparameters: dict[str, Any] | None = None,
        git_sha: str | None = None,
    ) -> int:
        """Insert a record and return the new trial count."""
        self.conn.execute(
            """
            INSERT INTO backtest_executions
                (layer_name, function_name, executed_at, git_sha, hyperparameters)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                layer_name,
                function_name,
                datetime.utcnow(),
                git_sha,
                json.dumps(hyperparameters or {}),
            ),
        )
        count = self.trial_count()
        logger.debug(
            "audit_record",
            layer=layer_name,
            function=function_name,
            trial_count=count,
        )
        return count

    def trial_count(self) -> int:
        """Return the monotonic trial count (row count of backtest_executions)."""
        row = self.conn.execute("SELECT COUNT(*) FROM backtest_executions").fetchone()
        return int(row[0]) if row else 0

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:  # pragma: no cover - defensive
            pass

    def __enter__(self) -> "AuditLog":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
