"""FastAPI application for the dashboard.

Run with::

    python scripts/run_api.py
    # or, from the repo root:
    PYTHONPATH=. uvicorn src.advisory.api.app:app --port 8000
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import live
from ..layer8_journal.entry import JournalEntryError

app = FastAPI(title="Market Advisory Dashboard API", version="0.1.0")

# The Vite dev server runs on a different origin; allow it directly so the app
# works whether or not the Vite proxy is in front of us.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class JournalEntryIn(BaseModel):
    ticker: str = Field(min_length=1, max_length=12)
    direction: str
    confidence: int = Field(ge=1, le=5)
    thesis: str = Field(min_length=1)
    primaryCatalyst: str | None = None
    invalidation: str | None = None
    expectedHorizon: int | None = Field(default=None, ge=1)


class JournalCloseIn(BaseModel):
    #: Realised P&L as a percentage (e.g. -3.1 for -3.1%); stored as a fraction.
    pnlPct: float
    exitReason: str | None = None
    thesisValidated: bool = True


class NoteIn(BaseModel):
    body: str = Field(min_length=1)
    ticker: str | None = Field(default=None, max_length=12)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/dashboard")
def dashboard() -> dict[str, Any]:
    """The full payload the React app loads on mount."""
    return live.build_dashboard()


@app.post("/api/journal")
def add_journal(entry: JournalEntryIn) -> dict[str, Any]:
    """Persist a new journal entry, then return the refreshed dashboard."""
    try:
        live.add_journal_entry(
            ticker=entry.ticker,
            direction=entry.direction,
            confidence=entry.confidence,
            thesis=entry.thesis,
            primary_catalyst=entry.primaryCatalyst,
            invalidation=entry.invalidation,
            expected_horizon=entry.expectedHorizon,
        )
    except JournalEntryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return live.build_dashboard()


@app.post("/api/journal/{entry_id}/close")
def close_journal(entry_id: str, body: JournalCloseIn) -> dict[str, Any]:
    """Close an open trade (records exit date, P&L, reason), then refresh."""
    try:
        live.close_journal_entry(
            entry_id=entry_id,
            pnl_pct=body.pnlPct / 100.0,
            exit_reason=body.exitReason,
            thesis_validated=body.thesisValidated,
        )
    except live.JournalEntryNotFound as exc:
        raise HTTPException(status_code=404, detail="Open trade not found") from exc
    return live.build_dashboard()


@app.post("/api/notes")
def add_note(note: NoteIn) -> dict[str, Any]:
    """Add a trader note to the inbox, then refresh."""
    live.add_note(body=note.body, ticker=note.ticker)
    return live.build_dashboard()


@app.post("/api/notes/{note_id}/read")
def read_note(note_id: str) -> dict[str, Any]:
    """Mark a note read, then refresh."""
    if not live.mark_note_read(note_id):
        raise HTTPException(status_code=404, detail="Note not found")
    return live.build_dashboard()
