"""Tier 3 #9 — Kronos probabilistic forecast, wired validated-only.

Loads the **promoted** (canonical) Kronos artifact only. Unlike the other live
modules, an unvalidated model is **hidden**, not shown with a disclosure: Kronos
is a new predictive claim, so it earns display only after it passes Layer 0 here
(see scripts/validate_kronos_candidate.py). When promoted, per-ticker forecasts
are attached to the watchlist assets as `assets[].kronos`.
"""
from __future__ import annotations

import threading
from typing import Any

import duckdb
import numpy as np

from config.settings import settings

from . import analogs_live

_LOCK = threading.Lock()
_cache: dict[str, Any] = {"path": None, "mtime": None, "forecaster": None}


def _promoted_forecaster():
    """Return the loaded promoted forecaster, or None (validated-only gate)."""
    path = settings.kronos_model_path_lite
    if not path.exists():
        return None
    from ..layer_kronos.forecaster import KronosForecaster

    with _LOCK:
        mtime = path.stat().st_mtime
        if _cache["forecaster"] is not None and _cache["path"] == str(path) and _cache["mtime"] == mtime:
            return _cache["forecaster"]
        f = KronosForecaster.load(path)
        _cache.update(path=str(path), mtime=mtime, forecaster=f)
        return f


def _returns(conn: duckdb.DuckDBPyConnection, ticker: str) -> np.ndarray:
    rows = conn.execute(
        "SELECT feature_value FROM features_pit WHERE ticker = ? AND feature_name = 'ret_1d' "
        "ORDER BY effective_date",
        [ticker],
    ).fetchall()
    return np.array([float(r[0]) for r in rows if r[0] is not None], dtype=float)


def _current_vol(conn: duckdb.DuckDBPyConnection, ticker: str) -> float | None:
    row = conn.execute(
        "SELECT feature_value FROM features_pit WHERE ticker = ? AND feature_name = 'realized_vol_21d' "
        "ORDER BY effective_date DESC LIMIT 1",
        [ticker],
    ).fetchone()
    return float(row[0]) if row and row[0] is not None else None


def compute_kronos(conn: duckdb.DuckDBPyConnection | None) -> dict[str, dict[str, Any]] | None:
    """Per-ticker Kronos forecasts, or None when no promoted model exists."""
    if conn is None:
        return None
    forecaster = _promoted_forecaster()
    if forecaster is None:
        return None  # validated-only: hidden until promoted
    out: dict[str, dict[str, Any]] = {}
    for ticker, _sector in analogs_live._WATCHLIST:
        try:
            returns = _returns(conn, ticker)
            if returns.size < 60:
                continue
            fc = forecaster.forecast(returns, current_vol_annual=_current_vol(conn, ticker))
            if fc is None:
                continue
            out[ticker] = {
                "forecast": fc["forecast"],
                "p5": fc["p5"], "p50": fc["p50"], "p95": fc["p95"],
                "pUp": fc["pUp"], "pVolShift": fc["pVolShift"],
                "validated": True,
            }
        except Exception:
            continue
    return out or None


def attach_to_assets(conn: duckdb.DuckDBPyConnection, assets: list[dict[str, Any]]) -> None:
    """Attach `kronos` to each watchlist asset in place, only if promoted."""
    k = compute_kronos(conn)
    if not k:
        return
    for a in assets:
        if a.get("ticker") in k:
            a["kronos"] = k[a["ticker"]]
