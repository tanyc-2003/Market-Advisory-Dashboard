"""Tier 3 #9 — Kronos forecast wiring, validated-only.

Loads the **promoted** Kronos artifact only (hidden until it passes Layer 0).
Two backends share one output contract:

* block-bootstrap → fast, computed on the GET path;
* transformer → heavy, precomputed out-of-band into ``kronos_forecast_cache``
  by ``scripts/kronos_forecast.py``; the GET path just reads the cache.

The transformer's candlesticks are reconstructed from the PIT ``px_*`` archive in
``features_pit``; an optional yfinance **live-edge** bar (the current, not-yet-
ingested day) may be appended for inference only — tagged ``liveEdge`` and never
written back into ``features_pit``.
"""
from __future__ import annotations

import json
import threading
from typing import Any

import duckdb
import numpy as np

from config.settings import settings

from . import analogs_live

_LOCK = threading.Lock()
_cache: dict[str, Any] = {"path": None, "mtime": None, "forecaster": None}

_PX = ["px_open", "px_high", "px_low", "px_close", "px_volume"]
_HORIZON = 10


# ---------------------------------------------------------------- model loading

def _promoted_forecaster():
    path = settings.kronos_model_path_lite
    if not path.exists():
        return None
    from ..layer_kronos.forecaster import load_forecaster

    with _LOCK:
        mtime = path.stat().st_mtime
        if _cache["forecaster"] is not None and _cache["path"] == str(path) and _cache["mtime"] == mtime:
            return _cache["forecaster"]
        f = load_forecaster(path)
        _cache.update(path=str(path), mtime=mtime, forecaster=f)
        return f


def _is_transformer(f) -> bool:
    return type(f).__name__ == "KronosTransformerForecaster"


# ---------------------------------------------------------------- data helpers

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


def _ohlcv_from_pit(conn: duckdb.DuckDBPyConnection, ticker: str, lookback: int):
    """(OHLCV DataFrame, x_timestamp Series) from the PIT px_* archive, or None."""
    import pandas as pd

    ph = ",".join("?" * len(_PX))
    rows = conn.execute(
        f"SELECT effective_date, feature_name, feature_value FROM features_pit "
        f"WHERE ticker = ? AND feature_name IN ({ph}) ORDER BY effective_date",
        [ticker, *_PX],
    ).fetchall()
    if not rows:
        return None
    by_date: dict[Any, dict[str, float]] = {}
    for d, fn, v in rows:
        if v is not None:
            by_date.setdefault(d, {})[fn] = float(v)
    recs = []
    for d in sorted(by_date):
        r = by_date[d]
        if all(k in r for k in _PX):
            recs.append((d, r["px_open"], r["px_high"], r["px_low"], r["px_close"], r["px_volume"]))
    if len(recs) < 60:
        return None
    recs = recs[-lookback:]
    df = pd.DataFrame(recs, columns=["date", "open", "high", "low", "close", "volume"])
    x_ts = pd.Series(pd.to_datetime(df["date"]).values)
    return df[["open", "high", "low", "close", "volume"]].reset_index(drop=True), x_ts


def _live_edge_bar(ticker: str):
    """Current not-yet-ingested bar from yfinance, or None. Never persisted."""
    try:
        from datetime import date, timedelta

        from ..data_infra.ingestion import YFinanceConnector

        end = date.today()
        raw = YFinanceConnector().fetch_daily_ohlcv([ticker], end - timedelta(days=7), end)
        if raw is None or raw.is_empty():
            return None
        import polars as pl

        last = raw.filter(pl.col("ticker") == ticker).sort("effective_date").tail(1)
        if last.is_empty():
            return None
        row = last.to_dicts()[0]
        return {k: row[k] for k in ("effective_date", "open", "high", "low", "close", "volume")}
    except Exception:
        return None


def assemble_ohlcv(conn, ticker: str, lookback: int, use_live_edge: bool):
    """Return (df, x_timestamp, y_timestamp, live_edge_used) or None."""
    import pandas as pd

    res = _ohlcv_from_pit(conn, ticker, lookback)
    if res is None:
        return None
    df, x_ts = res
    live_edge = False
    if use_live_edge:
        bar = _live_edge_bar(ticker)
        if bar and bar["effective_date"] > x_ts.iloc[-1].date():
            df = pd.concat([df, pd.DataFrame([{k: bar[k] for k in ("open", "high", "low", "close", "volume")}])],
                           ignore_index=True)
            x_ts = pd.concat([x_ts, pd.Series([pd.Timestamp(bar["effective_date"])])], ignore_index=True)
            live_edge = True
    last = x_ts.iloc[-1]
    y_ts = pd.Series(pd.bdate_range(last + pd.Timedelta(days=1), periods=_HORIZON))
    return df, x_ts, y_ts, live_edge


# ---------------------------------------------------------------- read paths

def _from_cache(conn: duckdb.DuckDBPyConnection) -> dict[str, dict[str, Any]] | None:
    try:
        rows = conn.execute("SELECT ticker, payload, live_edge FROM kronos_forecast_cache").fetchall()
    except Exception:
        return None
    out: dict[str, dict[str, Any]] = {}
    for tk, payload, live_edge in rows:
        p = json.loads(payload) if isinstance(payload, str) else payload
        out[tk] = {**p, "validated": True, "liveEdge": bool(live_edge)}
    return out or None


def compute_kronos(conn: duckdb.DuckDBPyConnection | None) -> dict[str, dict[str, Any]] | None:
    if conn is None:
        return None
    forecaster = _promoted_forecaster()
    if forecaster is None:
        return None  # validated-only: hidden until promoted
    if _is_transformer(forecaster):
        return _from_cache(conn)  # heavy backend served from the cache
    # Block-bootstrap backend: fast enough to run on the request path.
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
                "forecast": fc["forecast"], "p5": fc["p5"], "p50": fc["p50"], "p95": fc["p95"],
                "pUp": fc["pUp"], "pVolShift": fc["pVolShift"], "validated": True,
            }
        except Exception:
            continue
    return out or None


def attach_to_assets(conn: duckdb.DuckDBPyConnection, assets: list[dict[str, Any]]) -> None:
    k = compute_kronos(conn)
    if not k:
        return
    for a in assets:
        if a.get("ticker") in k:
            a["kronos"] = k[a["ticker"]]


# ---------------------------------------------------------------- refresh (out-of-band)

def refresh_cache(conn: duckdb.DuckDBPyConnection, use_live_edge: bool = True) -> int:
    """Recompute transformer forecasts into kronos_forecast_cache. Returns rows written."""
    forecaster = _promoted_forecaster()
    if forecaster is None or not _is_transformer(forecaster):
        return 0
    written = 0
    for ticker, _sector in analogs_live._WATCHLIST:
        asm = assemble_ohlcv(conn, ticker, forecaster.max_context, use_live_edge)
        if asm is None:
            continue
        df, x_ts, y_ts, live_edge = asm
        fc = forecaster.forecast(df, x_ts, y_ts, current_vol_annual=_current_vol(conn, ticker))
        if fc is None:
            continue
        conn.execute(
            "INSERT INTO kronos_forecast_cache (ticker, as_of, payload, live_edge, computed_at) "
            "VALUES (?, ?, ?, ?, now()) "
            "ON CONFLICT (ticker) DO UPDATE SET as_of = excluded.as_of, payload = excluded.payload, "
            "live_edge = excluded.live_edge, computed_at = now()",
            [ticker, x_ts.iloc[-1].date(), json.dumps(fc), live_edge],
        )
        written += 1
    return written
