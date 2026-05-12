"""JournalStore — DuckDB CRUD for JournalEntry objects."""
from __future__ import annotations

import json
from datetime import date
from typing import Any

import duckdb
import polars as pl

from .entry import JournalEntry


_COLUMNS: tuple[str, ...] = (
    "entry_id",
    "ticker",
    "entry_date",
    "direction",
    "thesis",
    "primary_catalyst",
    "invalidation",
    "expected_horizon",
    "confidence_self",
    "market_state_id",
    "analog_hit_rate",
    "analog_n",
    "contradictions",
    "unknowns_present",
    "exit_date",
    "pnl_pct",
    "thesis_validated",
    "exit_reason",
)


class JournalStore:
    """CRUD operations for :class:`JournalEntry` objects."""

    def __init__(self, conn: duckdb.DuckDBPyConnection):
        self.conn = conn

    # --- writes -----------------------------------------------------------

    def save(self, entry: JournalEntry) -> None:
        entry.validate()
        d = entry.to_dict()
        placeholders = ", ".join(["?"] * len(_COLUMNS))
        values = tuple(d[c] for c in _COLUMNS)
        self.conn.execute(
            f"INSERT OR REPLACE INTO journal_entries "
            f"({', '.join(_COLUMNS)}) VALUES ({placeholders})",
            values,
        )

    def close_trade(
        self,
        entry_id: str,
        exit_date: date,
        pnl_pct: float,
        exit_reason: str,
        thesis_validated: bool,
    ) -> None:
        self.conn.execute(
            """
            UPDATE journal_entries
            SET exit_date = ?, pnl_pct = ?, exit_reason = ?, thesis_validated = ?
            WHERE entry_id = ?
            """,
            (exit_date.isoformat(), pnl_pct, exit_reason, thesis_validated, entry_id),
        )

    # --- reads ------------------------------------------------------------

    def _rows_to_entries(self, rows: list[tuple[Any, ...]]) -> list[JournalEntry]:
        out: list[JournalEntry] = []
        for r in rows:
            d = dict(zip(_COLUMNS, r))
            contradictions = d.get("contradictions") or "[]"
            if isinstance(contradictions, str):
                try:
                    contradictions = json.loads(contradictions)
                except json.JSONDecodeError:
                    contradictions = []
            entry = JournalEntry(
                entry_id=d["entry_id"],
                ticker=d["ticker"],
                entry_date=d["entry_date"],
                direction=d["direction"],
                thesis=d["thesis"],
                primary_catalyst=d["primary_catalyst"],
                invalidation=d["invalidation"],
                expected_horizon=int(d["expected_horizon"]),
                confidence_self=int(d["confidence_self"]),
                market_state_id=d.get("market_state_id"),
                analog_hit_rate=d.get("analog_hit_rate"),
                analog_n=d.get("analog_n"),
                contradictions=list(contradictions),
                unknowns_present=bool(d.get("unknowns_present") or False),
                exit_date=d.get("exit_date"),
                pnl_pct=d.get("pnl_pct"),
                thesis_validated=d.get("thesis_validated"),
                exit_reason=d.get("exit_reason"),
            )
            out.append(entry)
        return out

    def get_open_trades(self) -> list[JournalEntry]:
        rows = self.conn.execute(
            f"SELECT {', '.join(_COLUMNS)} FROM journal_entries "
            "WHERE exit_date IS NULL"
        ).fetchall()
        return self._rows_to_entries(rows)

    def get_completed_trades(self) -> list[JournalEntry]:
        rows = self.conn.execute(
            f"SELECT {', '.join(_COLUMNS)} FROM journal_entries "
            "WHERE pnl_pct IS NOT NULL"
        ).fetchall()
        return self._rows_to_entries(rows)

    def get_all(self) -> list[JournalEntry]:
        rows = self.conn.execute(
            f"SELECT {', '.join(_COLUMNS)} FROM journal_entries"
        ).fetchall()
        return self._rows_to_entries(rows)

    def as_polars(self) -> pl.DataFrame:
        rows = self.conn.execute(
            f"SELECT {', '.join(_COLUMNS)} FROM journal_entries"
        ).fetchall()
        if not rows:
            return pl.DataFrame(schema={c: pl.Utf8 for c in _COLUMNS})
        cols: dict[str, list[Any]] = {c: [] for c in _COLUMNS}
        for r in rows:
            for c, v in zip(_COLUMNS, r):
                cols[c].append(v)
        return pl.DataFrame(cols)
