"""Backend service-layer the dashboard reads from.

The Streamlit pages never run computation themselves; they call helpers
in this module, which read pre-computed results from DuckDB and cache
them via ``@st.cache_data`` at the call sites.
"""
from __future__ import annotations

from datetime import date
from typing import Iterable

import duckdb
import polars as pl

from config.settings import settings
from src.advisory.layer0_validation.report import (
    ValidationReport,
    load_latest_report,
    persist_report,
)
from src.advisory.layer8_journal.store import JournalStore


def open_main_conn(db_path: str | None = None) -> duckdb.DuckDBPyConnection:
    """Open a DuckDB connection to the main store.  Path defaults to settings."""
    path = db_path or str(settings.main_db_path)
    return duckdb.connect(path)


def get_validation_report(
    conn: duckdb.DuckDBPyConnection, layer_name: str
) -> ValidationReport | None:
    """Return the latest persisted report for ``layer_name`` or None."""
    return load_latest_report(conn, layer_name)


def list_layer_status_rows(
    conn: duckdb.DuckDBPyConnection,
    layer_names: Iterable[str] | None = None,
) -> list[dict]:
    """Return a list of rows suitable for the validation status table.

    Each row carries layer name, status, walk-forward Sharpe, CPCV p30,
    DSR, survivorship coverage, paper-trade divergence (None when N/A).
    """
    layer_names = list(layer_names or _DEFAULT_LAYERS)
    out: list[dict] = []
    for name in layer_names:
        report = load_latest_report(conn, name)
        if report is None:
            out.append(
                {
                    "layer": name,
                    "status": "no_report",
                    "walk_forward_sharpe": None,
                    "cpcv_p30_sharpe": None,
                    "deflated_sharpe": None,
                    "survivorship_coverage": None,
                    "rationale": "No validation report persisted yet.",
                }
            )
            continue
        out.append(
            {
                "layer": name,
                "status": report.status,
                "walk_forward_sharpe": report.walk_forward_sharpe,
                "cpcv_p30_sharpe": report.cpcv_p30_sharpe,
                "deflated_sharpe": report.deflated_sharpe,
                "survivorship_coverage": report.survivorship_coverage,
                "rationale": report.rationale,
            }
        )
    return out


_DEFAULT_LAYERS: tuple[str, ...] = (
    "layer0",
    "layer1",
    "layer2",
    "layer3",
    "layer4",
    "layer5",
    "layer6",
    "layer7",
    "layer8_journal",
    "layer9_calibration",
    "layer10_sizing",
)


def get_journal_store(conn: duckdb.DuckDBPyConnection) -> JournalStore:
    return JournalStore(conn)


def get_journal_polars(conn: duckdb.DuckDBPyConnection) -> pl.DataFrame:
    return JournalStore(conn).as_polars()


def get_latest_paper_trade_pnl(
    conn: duckdb.DuckDBPyConnection,
    layer_name: str,
    limit: int = 365,
) -> pl.DataFrame:
    """Return the most recent ``limit`` paper-trade days for a layer."""
    rows = conn.execute(
        """
        SELECT entry_date, pnl_pct
        FROM paper_trade_performance
        WHERE layer_attributed_to = ?
          AND pnl_pct IS NOT NULL
        ORDER BY entry_date DESC
        LIMIT ?
        """,
        (layer_name, limit),
    ).fetchall()
    if not rows:
        return pl.DataFrame(schema={"entry_date": pl.Date, "pnl_pct": pl.Float64})
    return pl.DataFrame(
        {
            "entry_date": [r[0] for r in rows],
            "pnl_pct": [float(r[1]) for r in rows],
        }
    )


def is_data_stale(as_of: date, today: date, max_trading_days: int = 2) -> bool:
    """Return True if ``as_of`` is more than ``max_trading_days`` business
    days before ``today``.  Used by the sidebar staleness banner.
    """
    cursor = today
    skipped = 0
    while skipped < max_trading_days and cursor > as_of:
        cursor = cursor.fromordinal(cursor.toordinal() - 1)
        if cursor.weekday() < 5:
            skipped += 1
    return as_of < cursor


def persist_validation_report(
    conn: duckdb.DuckDBPyConnection, report: ValidationReport
) -> None:
    persist_report(conn, report)
