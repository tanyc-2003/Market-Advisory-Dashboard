"""Tier 1 #1 — system self-grading track record.

The system logs each watchlist call *as stated* (per ticker, per as-of date),
then resolves it against the realised forward return once the horizon has
elapsed. ``ret_fwd_10d`` at a date T *is* the realised forward return (only
knowable at T+10), so resolution is a point-in-time-honest read once T+10 has
data. The dashboard then reports how the system's own calls have actually done.

Emission is explicit (``scripts/track_record.py`` / the helpers here), never on
the GET path, so reads stay side-effect free.
"""
from __future__ import annotations

import hashlib
from datetime import date
from typing import Any

import duckdb
import numpy as np

from . import analogs_live

HORIZON_DAYS = 10
BENCHMARK = "SPY"
MIN_RESOLVED = 20  # below this, fall back to representative


def _prediction_id(ticker: str, knowledge_date, horizon: int) -> str:
    return hashlib.sha1(f"{ticker}|{knowledge_date}|{horizon}".encode()).hexdigest()


def analog_forecast(conn: duckdb.DuckDBPyConnection, ticker: str, as_of) -> dict[str, Any] | None:
    """Point-in-time analog forecast for ``ticker`` as of ``as_of`` (a date)."""
    from ..layer2_analogs.engine import HistoricalAnalogEngine

    hist = analogs_live._ticker_history(conn, ticker, as_of=as_of)
    if hist is None or hist.height < 60:
        return None
    anchor_date = hist["effective_date"][-1]
    query = hist.select(analogs_live._DISTANCE_FEATURES).to_numpy()[-1]
    engine = HistoricalAnalogEngine(feature_cols=analogs_live._DISTANCE_FEATURES, app_mode="v7_lite")
    result = engine.find_analogs(
        hist, query, anchor_date, k=analogs_live._K, forward_return_col=analogs_live._FWD, ticker=ticker
    )
    fwd = np.asarray(result.forward_returns, dtype=float)
    fwd = fwd[np.isfinite(fwd)]
    if fwd.size < 5:
        return None
    p5, p50, p95 = (float(np.percentile(fwd, q)) for q in (5, 50, 95))
    eff_n = float(result.effective_n_recency_weighted)
    sizing = analogs_live._kelly_ladder(fwd, float(result.hit_rate), eff_n)
    return {
        "knowledge_date": anchor_date,
        "pred_p50": p50,
        "pred_p5": p5,
        "pred_p95": p95,
        "pred_hit_prob": float(result.hit_rate),
        "pred_sizing": float(sizing["displayed"]),
        "effective_n": eff_n,
    }


def emit_prediction(conn: duckdb.DuckDBPyConnection, ticker: str, as_of) -> bool:
    """Log one prediction (idempotent per ticker+knowledge_date). Returns True if written."""
    fc = analog_forecast(conn, ticker, as_of)
    if fc is None:
        return False
    pid = _prediction_id(ticker, fc["knowledge_date"], HORIZON_DAYS)
    conn.execute(
        """
        INSERT INTO system_predictions
            (prediction_id, ticker, knowledge_date, horizon_days,
             pred_p50, pred_p5, pred_p95, pred_hit_prob, pred_sizing, effective_n)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (prediction_id) DO NOTHING
        """,
        [
            pid, ticker, fc["knowledge_date"], HORIZON_DAYS,
            fc["pred_p50"], fc["pred_p5"], fc["pred_p95"],
            fc["pred_hit_prob"], fc["pred_sizing"], fc["effective_n"],
        ],
    )
    return True


def resolve(conn: duckdb.DuckDBPyConnection) -> int:
    """Resolve predictions whose horizon has fully elapsed. Returns count resolved."""
    unresolved = conn.execute(
        "SELECT prediction_id, ticker, knowledge_date, horizon_days FROM system_predictions "
        "WHERE resolved = FALSE"
    ).fetchall()
    resolved = 0
    for pid, ticker, kdate, horizon in unresolved:
        # Only resolve once at least `horizon` trading days exist after kdate.
        n_after = conn.execute(
            "SELECT count(DISTINCT effective_date) FROM features_pit "
            "WHERE ticker = ? AND effective_date > ?",
            [ticker, kdate],
        ).fetchone()[0]
        if n_after < horizon:
            continue
        realized = conn.execute(
            "SELECT feature_value FROM features_pit "
            "WHERE ticker = ? AND feature_name = 'ret_fwd_10d' AND effective_date = ?",
            [ticker, kdate],
        ).fetchone()
        if realized is None or realized[0] is None:
            continue
        bench = conn.execute(
            "SELECT feature_value FROM features_pit "
            "WHERE ticker = ? AND feature_name = 'ret_fwd_10d' AND effective_date = ?",
            [BENCHMARK, kdate],
        ).fetchone()
        realized_ret = float(realized[0])
        bench_ret = float(bench[0]) if bench and bench[0] is not None else None
        alpha = realized_ret - bench_ret if bench_ret is not None else None
        conn.execute(
            "UPDATE system_predictions SET resolved = TRUE, resolved_at = ?, "
            "realized_ret = ?, benchmark_ret = ?, alpha = ? WHERE prediction_id = ?",
            [date.today(), realized_ret, bench_ret, alpha, pid],
        )
        resolved += 1
    return resolved


def compute_track_record(conn: duckdb.DuckDBPyConnection | None) -> dict[str, Any] | None:
    if conn is None:
        return None
    try:
        rows = conn.execute(
            "SELECT ticker, pred_p50, pred_hit_prob, realized_ret, alpha "
            "FROM system_predictions WHERE resolved = TRUE AND realized_ret IS NOT NULL"
        ).fetchall()
        pending = conn.execute(
            "SELECT count(*) FROM system_predictions WHERE resolved = FALSE"
        ).fetchone()[0]
    except Exception:
        return None
    if len(rows) < MIN_RESOLVED:
        return None

    pred_p50 = np.array([r[1] for r in rows], dtype=float)
    hit_prob = np.array([r[2] for r in rows], dtype=float)
    realized = np.array([r[3] for r in rows], dtype=float)
    alphas = np.array([r[4] for r in rows if r[4] is not None], dtype=float)

    up = realized > 0
    directional = np.sign(pred_p50) == np.sign(realized)

    # Reliability: bucket predicted P(up) into deciles vs. observed up-rate.
    reliability: list[dict[str, Any]] = []
    edges = np.linspace(0.0, 1.0, 6)
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (hit_prob >= lo) & (hit_prob < hi if hi < 1.0 else hit_prob <= hi)
        if mask.sum() == 0:
            continue
        reliability.append(
            {"bucket": round(float((lo + hi) / 2), 2),
             "predicted": round(float(hit_prob[mask].mean()), 4),
             "observed": round(float(up[mask].mean()), 4),
             "n": int(mask.sum())}
        )

    by_ticker: list[dict[str, Any]] = []
    for tk in sorted({r[0] for r in rows}):
        idx = [i for i, r in enumerate(rows) if r[0] == tk]
        tk_real = realized[idx]
        tk_alpha = np.array([rows[i][4] for i in idx if rows[i][4] is not None], dtype=float)
        by_ticker.append(
            {"ticker": tk, "n": len(idx),
             "hitRate": round(float((tk_real > 0).mean()), 4),
             "alpha": round(float(tk_alpha.mean()), 4) if tk_alpha.size else None}
        )

    return {
        "resolved": len(rows),
        "pending": int(pending),
        "hitRate": round(float(up.mean()), 4),
        "directionalAccuracy": round(float(directional.mean()), 4),
        "meanPredP50": round(float(pred_p50.mean()), 4),
        "meanRealized": round(float(realized.mean()), 4),
        "alphaMean": round(float(alphas.mean()), 4) if alphas.size else None,
        "alphaHitRate": round(float((alphas > 0).mean()), 4) if alphas.size else None,
        "byTicker": by_ticker,
        "reliability": reliability,
        "source": "live",
    }
