"""Real backend wiring + dashboard payload assembly.

Each helper returns a value plus, where relevant, a ``live`` flag. When a real
DuckDB store is present the value is computed from it; otherwise the function
falls back to :mod:`presentation` so the dashboard never renders empty.
"""
from __future__ import annotations

import uuid
from datetime import date
from typing import Any

import duckdb

from config.settings import settings

from . import db, presentation

# Map the design's L0..L10 ids onto the persisted validation-report layer names.
LAYER_NAME_MAP: dict[str, str] = {
    "L0": "layer0", "L1": "layer1", "L2": "layer2", "L3": "layer3", "L4": "layer4",
    "L5": "layer5", "L6": "layer6", "L7": "layer7", "L8": "layer8_journal",
    "L9": "layer9_calibration", "L10": "layer10_sizing",
}


# ---------------------------------------------------------------- meta

def meta(conn: duckdb.DuckDBPyConnection | None) -> dict[str, Any]:
    as_of = presentation.AS_OF
    if conn is not None:
        try:
            row = conn.execute("SELECT max(effective_date) FROM features_pit").fetchone()
            if row and row[0]:
                d = row[0]
                as_of = f"{d:%b} {d.day}, {d.year}"
        except Exception:
            pass
    return {
        "asOf": as_of,
        "appMode": settings.app_mode,
        "developerMode": settings.developer_mode,
        "llmEnabled": settings.llm_enabled,
        "kellyCap": f"{settings.kelly_absolute_cap:.2f}",
    }


# ---------------------------------------------------------------- layers

def layers(conn: duckdb.DuckDBPyConnection | None) -> list[dict[str, Any]]:
    """Representative layer set, overlaid with any real validation reports.

    No reports exist until ``run_validation.py`` runs, so today this returns the
    representative set unchanged; as reports are persisted they override the
    matching rows automatically.
    """
    base = presentation.layers()
    if conn is None:
        return base
    try:
        from ..layer0_validation.report import load_latest_report

        for layer in base:
            name = LAYER_NAME_MAP.get(layer["id"])
            if not name:
                continue
            rep = load_latest_report(conn, name)
            if rep is None:
                continue
            layer["status"] = rep.status
            layer["sharpe"] = rep.walk_forward_sharpe
            layer["ece"] = rep.walk_forward_ece
            layer["p30"] = rep.cpcv_p30_sharpe
            layer["dsr"] = rep.deflated_sharpe
            layer["rationale"] = rep.rationale or layer["rationale"]
    except Exception:
        pass
    return base


# ---------------------------------------------------------------- validation summaries

def survivorship_coverage(conn: duckdb.DuckDBPyConnection | None) -> tuple[str, bool]:
    if conn is None:
        return presentation.SURVIVORSHIP_COVERAGE_FALLBACK, False
    try:
        import polars as pl

        from ..layer0_validation.survivorship import SurvivorshipAuditor

        live_rows = conn.execute("SELECT DISTINCT ticker FROM features_pit").fetchall()
        del_rows = conn.execute(
            "SELECT ticker, termination_date FROM delisted_tickers"
        ).fetchall()
        win = conn.execute(
            "SELECT min(effective_date), max(effective_date) FROM features_pit"
        ).fetchone()
        if not live_rows or not del_rows or not win or win[0] is None:
            return presentation.SURVIVORSHIP_COVERAGE_FALLBACK, False

        live_df = pl.DataFrame({"ticker": [r[0] for r in live_rows]})
        del_df = pl.DataFrame(
            {
                "ticker": [r[0] for r in del_rows],
                "termination_date": [r[1] for r in del_rows],
            }
        )
        result = SurvivorshipAuditor(coverage_floor=0.95).audit(
            live_df, del_df, win[0], win[1]
        )
        return f"{result['coverage']:.3f}", True
    except Exception:
        return presentation.SURVIVORSHIP_COVERAGE_FALLBACK, False


def dsr_trials() -> tuple[str, bool]:
    if not db.audit_db_exists():
        return presentation.DSR_TRIALS_FALLBACK, False
    try:
        from ..layer0_validation.audit_log import AuditLog

        log = AuditLog(settings.audit_db_path)
        try:
            count = log.trial_count()
        finally:
            log.close()
        if count <= 0:
            return presentation.DSR_TRIALS_FALLBACK, False
        return f"{count:,}", True
    except Exception:
        return presentation.DSR_TRIALS_FALLBACK, False


# ---------------------------------------------------------------- journal

def _open_to_dict(e: Any) -> dict[str, Any]:
    opened = e.entry_date
    if isinstance(opened, date):
        opened = f"{opened:%b} {opened.day}"
    return {
        "id": e.entry_id,
        "ticker": e.ticker,
        "direction": e.direction,
        "conf": int(e.confidence_self),
        "thesis": e.thesis,
        "opened": str(opened),
    }


def _closed_to_dict(e: Any) -> dict[str, Any]:
    if e.exit_reason:
        outcome = e.exit_reason
    elif e.thesis_validated:
        outcome = "Thesis confirmed"
    else:
        outcome = "Invalidated"
    pnl = "—"
    if e.pnl_pct is not None:
        pnl = f"{e.pnl_pct * 100:+.1f}%"
    return {
        "ticker": e.ticker,
        "direction": e.direction,
        "outcome": outcome,
        "pnl": pnl,
    }


def journal(conn: duckdb.DuckDBPyConnection | None) -> tuple[dict[str, Any], bool]:
    if conn is None:
        return presentation.journal(), False
    try:
        from ..layer8_journal.store import JournalStore

        store = JournalStore(conn)
        opens = store.get_open_trades()
        closed = store.get_completed_trades()
    except Exception:
        return presentation.journal(), False

    if not opens and not closed:
        # No real entries yet — show the representative journal until the user logs one.
        return presentation.journal(), False
    return (
        {
            "open": [_open_to_dict(e) for e in opens],
            "closed": [_closed_to_dict(e) for e in closed],
        },
        True,
    )


def add_journal_entry(
    *,
    ticker: str,
    direction: str,
    confidence: int,
    thesis: str,
    primary_catalyst: str | None = None,
    invalidation: str | None = None,
    expected_horizon: int | None = None,
) -> None:
    """Persist a new journal entry. Raises JournalEntryError on invalid input."""
    from ..layer8_journal.entry import JournalEntry
    from ..layer8_journal.store import JournalStore

    with db.LOCK:
        conn = db.get_main_conn(create=True)
        assert conn is not None  # create=True guarantees a connection
        entry = JournalEntry(
            entry_id=uuid.uuid4().hex,
            ticker=ticker.strip().upper(),
            entry_date=date.today(),
            direction=direction.strip().lower(),
            thesis=thesis.strip(),
            primary_catalyst=(primary_catalyst or "Not specified").strip() or "Not specified",
            invalidation=(invalidation or "Not specified").strip() or "Not specified",
            expected_horizon=int(expected_horizon or 10),
            confidence_self=int(confidence),
        )
        entry.validate()  # raises JournalEntryError before any write
        JournalStore(conn).save(entry)


class JournalEntryNotFound(KeyError):
    """Raised when closing an entry id that has no matching open trade."""


def close_journal_entry(
    *,
    entry_id: str,
    pnl_pct: float,
    exit_reason: str | None = None,
    thesis_validated: bool = True,
) -> None:
    """Close an open trade. ``pnl_pct`` is a fraction (e.g. 0.042 for +4.2%)."""
    from ..layer8_journal.store import JournalStore

    with db.LOCK:
        conn = db.get_main_conn(create=False)
        if conn is None:
            raise JournalEntryNotFound(entry_id)
        store = JournalStore(conn)
        open_ids = {e.entry_id for e in store.get_open_trades()}
        if entry_id not in open_ids:
            raise JournalEntryNotFound(entry_id)
        store.close_trade(
            entry_id=entry_id,
            exit_date=date.today(),
            pnl_pct=float(pnl_pct),
            exit_reason=(exit_reason or "Closed").strip() or "Closed",
            thesis_validated=bool(thesis_validated),
        )


# ---------------------------------------------------------------- assembly

def build_dashboard() -> dict[str, Any]:
    """Assemble the full payload the React app consumes from GET /api/dashboard."""
    with db.LOCK:
        conn = db.get_main_conn(create=False)
        layer_rows = layers(conn)
        coverage, _ = survivorship_coverage(conn)
        trials, _ = dsr_trials()
        journal_view, _ = journal(conn)
        meta_block = meta(conn)

    meta_block["gate"] = {
        "production": sum(1 for layer in layer_rows if layer["status"] == "production"),
        "preview": sum(1 for layer in layer_rows if layer["status"] == "research_preview"),
    }
    meta_block["live"] = db.main_db_exists()

    return {
        "meta": meta_block,
        "layers": layer_rows,
        "marketState": presentation.market_state(),
        "assets": presentation.assets(),
        "alerts": presentation.alerts(),
        "unknowns": presentation.unknowns(),
        "sizingNote": presentation.SIZING_NOTE,
        "portfolio": presentation.portfolio(),
        "journal": journal_view,
        "calibration": presentation.calibration(),
        "validation": {"survivorshipCoverage": coverage, "dsrTrials": trials},
    }
