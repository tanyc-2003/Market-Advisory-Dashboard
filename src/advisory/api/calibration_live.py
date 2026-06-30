"""Live Layer 9 — calibration from closed journal entries.

Grades the trader's self-reported confidence against realised outcomes. Each
closed journal entry carries a confidence band (1-5) and a ``thesis_validated``
flag; we map each band to an implied probability, then compare implied vs
observed success rates to produce the reliability table, Brier score, ECE and a
thesis-drift check.

Returns ``None`` (→ representative fallback) until enough graded entries exist,
so the page is never empty or misleading on a fresh journal.
"""
from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any

import duckdb

# Confidence band → implied probability the band asserts (matches the design).
_IMPLIED: dict[int, float] = {1: 0.30, 2: 0.45, 3: 0.55, 4: 0.70, 5: 0.85}

# Minimum graded entries before live calibration replaces representative data.
_MIN_GRADED = 5

# Thesis-drift: invalidated-and-lost trades in the trailing window over threshold.
_DRIFT_WINDOW_DAYS = 30
_DRIFT_THRESHOLD = 3


def _wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    phat = k / n
    denom = 1.0 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    half = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n)) / denom
    return max(0.0, center - half), min(1.0, center + half)


def _coerce_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def compute_calibration(conn: duckdb.DuckDBPyConnection | None) -> dict[str, Any] | None:
    if conn is None:
        return None
    try:
        rows = conn.execute(
            """
            SELECT confidence_self, thesis_validated, pnl_pct, exit_date
            FROM journal_entries
            WHERE exit_date IS NOT NULL AND thesis_validated IS NOT NULL
            """
        ).fetchall()
    except Exception:
        return None

    graded = [r for r in rows if r[0] is not None]
    if len(graded) < _MIN_GRADED:
        return None

    # Per-band aggregation.
    by_band: dict[int, list[tuple[int, float | None, Any]]] = {}
    for conf, validated, pnl, exit_d in graded:
        band = int(conf)
        if band not in _IMPLIED:
            continue
        by_band.setdefault(band, []).append((1 if validated else 0, pnl, exit_d))

    total = sum(len(v) for v in by_band.values())
    if total < _MIN_GRADED:
        return None

    table_rows: list[dict[str, Any]] = []
    brier_terms: list[float] = []
    ece = 0.0
    for band in sorted(by_band):
        entries = by_band[band]
        n = len(entries)
        wins = sum(e[0] for e in entries)
        observed = wins / n
        implied = _IMPLIED[band]
        lo, hi = _wilson_ci(wins, n)
        table_rows.append(
            {"band": str(band), "implied": implied, "observed": observed, "lo": lo, "hi": hi, "n": n}
        )
        ece += (n / total) * abs(observed - implied)
        brier_terms.extend((implied - e[0]) ** 2 for e in entries)

    brier = sum(brier_terms) / len(brier_terms) if brier_terms else 0.0

    # Thesis drift: invalidated-and-lost trades in the trailing window.
    cutoff = date.today() - timedelta(days=_DRIFT_WINDOW_DAYS)
    drift_count = 0
    for _conf, validated, pnl, exit_d in graded:
        d = _coerce_date(exit_d)
        if d is None or d < cutoff:
            continue
        if not validated and pnl is not None and float(pnl) < 0:
            drift_count += 1
    drift_detected = drift_count > _DRIFT_THRESHOLD
    if drift_detected:
        drift = (
            f"{drift_count} invalidated-and-lost trades in the last {_DRIFT_WINDOW_DAYS} days exceeds "
            f"the threshold of {_DRIFT_THRESHOLD} — high-confidence calls are not surviving contact "
            "with the market."
        )
    else:
        drift = (
            f"{drift_count} invalidated-and-lost trade(s) in the last {_DRIFT_WINDOW_DAYS} days, within "
            f"the threshold of {_DRIFT_THRESHOLD}."
        )

    ece_note = (
        "Above the 0.05 ceiling — overconfident." if ece > 0.05 else "Within the 0.05 ceiling."
    )
    if total < 15:
        n_note = f"Below the 15-entry minimum — treat with caution."
    elif total < 30:
        n_note = "Above the 15-entry minimum, below comfort."
    else:
        n_note = "Sufficient sample."

    cards = [
        {"label": "Brier score", "value": f"{brier:.3f}", "note": "Lower is better. 0.25 = coin flip."},
        {"label": "Expected calibration error", "value": f"{ece:.3f}", "note": ece_note},
        {"label": "Graded entries", "value": str(total), "note": n_note},
    ]

    return {
        "cards": cards,
        "rows": table_rows,
        "drift": drift,
        "driftDetected": drift_detected,
        "source": "live",
    }
