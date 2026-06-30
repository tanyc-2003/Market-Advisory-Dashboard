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
