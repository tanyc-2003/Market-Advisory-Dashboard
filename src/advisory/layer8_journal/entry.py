"""JournalEntry dataclass with self-validation."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any


VALID_DIRECTIONS: tuple[str, ...] = ("long", "short", "avoided")
MIN_CONFIDENCE: int = 1
MAX_CONFIDENCE: int = 5


class JournalEntryError(ValueError):
    """Raised when a :class:`JournalEntry` fails its self-validation."""


@dataclass
class JournalEntry:
    entry_id: str
    ticker: str
    entry_date: date
    direction: str
    thesis: str
    primary_catalyst: str
    invalidation: str
    expected_horizon: int
    confidence_self: int
    market_state_id: int | None = None
    analog_hit_rate: float | None = None
    analog_n: int | None = None
    contradictions: list[str] = field(default_factory=list)
    unknowns_present: bool = False
    exit_date: date | None = None
    pnl_pct: float | None = None
    thesis_validated: bool | None = None
    exit_reason: str | None = None

    def validate(self) -> None:
        if self.direction not in VALID_DIRECTIONS:
            raise JournalEntryError(
                f"direction must be one of {VALID_DIRECTIONS}; got {self.direction!r}"
            )
        if not (MIN_CONFIDENCE <= self.confidence_self <= MAX_CONFIDENCE):
            raise JournalEntryError(
                f"confidence_self must be in [{MIN_CONFIDENCE}, {MAX_CONFIDENCE}]; "
                f"got {self.confidence_self}"
            )
        if self.expected_horizon <= 0:
            raise JournalEntryError(
                f"expected_horizon must be positive; got {self.expected_horizon}"
            )
        if not self.thesis or not self.thesis.strip():
            raise JournalEntryError("thesis cannot be blank")

    @property
    def is_complete(self) -> bool:
        return self.exit_date is not None and self.pnl_pct is not None

    def to_dict(self) -> dict[str, Any]:
        """Serialise for DuckDB insertion."""
        d: dict[str, Any] = asdict(self)
        d["entry_date"] = self.entry_date.isoformat()
        d["exit_date"] = self.exit_date.isoformat() if self.exit_date else None
        d["contradictions"] = json.dumps(self.contradictions)
        return d
