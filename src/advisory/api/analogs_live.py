"""Live Layers 2 (+ 10) — historical-analog watchlist over real data.

For each watchlist ticker we run the :class:`HistoricalAnalogEngine` over its
real feature history: find the 30 nearest past days under a shrinkage-stabilised
Mahalanobis distance, then summarise those days' forward 10-day returns into the
percentile distribution, hit rate and recency-weighted effective N the design's
watchlist shows. We also:

  * derive the top drivers from the current state's feature z-scores,
  * run the dual-pass global-vs-within-regime disagreement check (conditioning
    on the live HMM market state), and
  * compute a tail-aware Kelly ladder for the sizing panel (Layer 10), capped at
    the architecture's KELLY_ABSOLUTE_CAP.

Everything carries the same research-preview framing as the rest of the lite
tier — the analog engine has no Layer 0 predictive sign-off.
"""
from __future__ import annotations

import threading
from typing import Any

import duckdb
import numpy as np

from config.settings import settings

# Single-name tickers in the ingested universe (macro proxies excluded).
_WATCHLIST: list[tuple[str, str]] = [
    ("NVDA", "Semiconductors"),
    ("MSFT", "Software"),
    ("AAPL", "Consumer Tech"),
    ("GOOGL", "Internet"),
    ("AMZN", "E-commerce"),
]

# Features used for the analog distance (per-ticker, exclude forward return + VIX).
_DISTANCE_FEATURES: list[str] = [
    "ret_1d",
    "ret_5d",
    "ret_21d",
    "ret_63d",
    "realized_vol_21d",
    "pct_above_ma50",
    "rsi_14",
]
_FWD = "ret_fwd_10d"
_K = 30

_LOCK = threading.Lock()
_cache: dict[str, Any] = {"key": None, "value": None}


def _ticker_history(conn: duckdb.DuckDBPyConnection, ticker: str):
    import polars as pl

    feats = _DISTANCE_FEATURES + [_FWD]
    cols = ", ".join(f"'{c}'" for c in feats)
    rows = conn.execute(
        f"""
        SELECT effective_date, feature_name, feature_value
        FROM features_pit
        WHERE ticker = ? AND feature_name IN ({cols})
        ORDER BY effective_date
        """,
        [ticker],
    ).fetchall()
    if not rows:
        return None
    df = (
        pl.DataFrame(
            {
                "effective_date": [r[0] for r in rows],
                "feature_name": [r[1] for r in rows],
                "value": [float(r[2]) if r[2] is not None else None for r in rows],
            }
        )
        .pivot(values="value", index="effective_date", on="feature_name")
        .sort("effective_date")
    )
    if any(c not in df.columns for c in _DISTANCE_FEATURES):
        return None
    # Need the distance features present on every candidate row; forward return
    # is allowed null (the most recent ~10 rows have no realised forward yet, and
    # the engine excludes them via min-separation anyway).
    return df.drop_nulls(subset=_DISTANCE_FEATURES)


def _market_state_path(conn: duckdb.DuckDBPyConnection):
    """date -> HMM state map and the current state, or (None, None) if no model."""
    try:
        from . import market_state_live

        engine, _ = market_state_live._load_engine()
        if engine is None:
            return None, None, None
        window = market_state_live._recent_window(conn, engine.feature_cols, limit=100_000)
        if window is None or window.height == 0:
            return None, None, None
        path = np.asarray(engine.decode_path(window))
        dates = window["effective_date"].to_list()
        state_map = {d: int(s) for d, s in zip(dates, path)}
        return engine, state_map, int(path[-1])
    except Exception:
        return None, None, None


def _drivers(query: np.ndarray, hist_x: np.ndarray, cols: list[str], n: int = 3) -> list[str]:
    mu = hist_x.mean(axis=0)
    sd = hist_x.std(axis=0)
    sd = np.where(sd > 0, sd, 1.0)
    z = (query - mu) / sd
    order = np.argsort(-np.abs(z))[:n]
    return [f"{cols[i]} {'↑' if z[i] >= 0 else '↓'}" for i in order]


def _kelly_ladder(fwd: np.ndarray, hit_rate: float, effective_n: float) -> dict[str, float]:
    """Tail-aware Kelly ladder from the analog forward-return distribution."""
    wins = fwd[fwd > 0]
    losses = fwd[fwd < 0]
    avg_win = float(wins.mean()) if wins.size else 0.0
    avg_loss = float(-losses.mean()) if losses.size else 0.0
    if avg_win > 0 and avg_loss > 0:
        b = avg_win / avg_loss
        f = hit_rate - (1.0 - hit_rate) / b
    else:
        f = 0.0
    raw = float(np.clip(f, 0.0, 1.0))
    std = raw * 0.5  # standard half-Kelly haircut
    regime_factor = float(np.clip(effective_n / _K, 0.3, 1.0))  # less evidence -> bigger haircut
    regime = std * regime_factor
    displayed = min(regime, settings.kelly_absolute_cap)
    return {"raw": raw, "std": std, "regime": regime, "displayed": displayed}


def _conf(effective_n: float) -> str:
    if effective_n >= 20:
        return "moderate"
    if effective_n >= 12:
        return "weak"
    return "insufficient"


def _asset(conn, ticker: str, sector: str, ms_engine, state_map, current_state) -> dict[str, Any] | None:
    import polars as pl

    from ..layer2_analogs.engine import HistoricalAnalogEngine

    hist = _ticker_history(conn, ticker)
    if hist is None or hist.height < 60:
        return None

    anchor_date = hist["effective_date"][-1]
    query = hist.select(_DISTANCE_FEATURES).to_numpy()[-1]
    hist_x = hist.select(_DISTANCE_FEATURES).to_numpy()

    engine = HistoricalAnalogEngine(feature_cols=_DISTANCE_FEATURES, app_mode="v7_lite")

    disagreement = False
    note: str | None = None
    if state_map is not None and current_state is not None:
        states = [state_map.get(d) for d in hist["effective_date"].to_list()]
        hist_s = hist.with_columns(pl.Series("hmm_state", states)).drop_nulls(subset=["hmm_state"])
        try:
            dis = engine.find_analogs_with_disagreement(
                hist_s, query, anchor_date, dominant_state_id=current_state, k=_K, forward_return_col=_FWD
            )
            result = dis.global_set
            overlap = dis.overlap_pct
            if overlap < 0.5 and result.forward_returns.size:
                disagreement = True
                note = (
                    f"Global vs within-regime analogs overlap only {overlap * 100:.0f}% — "
                    "conditioning on the current market state materially changes the picture."
                )
        except Exception:
            result = engine.find_analogs(hist, query, anchor_date, k=_K, forward_return_col=_FWD, ticker=ticker)
    else:
        result = engine.find_analogs(hist, query, anchor_date, k=_K, forward_return_col=_FWD, ticker=ticker)

    fwd = np.asarray(result.forward_returns, dtype=float)
    fwd = fwd[np.isfinite(fwd)]
    if fwd.size < 5:
        return None

    p5, p25, p50, p75, p95 = (float(np.percentile(fwd, q)) for q in (5, 25, 50, 75, 95))
    eff_n = float(result.effective_n_recency_weighted)

    asset: dict[str, Any] = {
        "ticker": ticker,
        "sector": sector,
        "n": int(round(eff_n)),
        "hitRate": float(result.hit_rate),
        "conf": _conf(eff_n),
        "p5": p5, "p25": p25, "p50": p50, "p75": p75, "p95": p95,
        "disagreement": disagreement,
        "drivers": _drivers(query, hist_x, _DISTANCE_FEATURES),
        "sizing": _kelly_ladder(fwd, float(result.hit_rate), eff_n),
    }
    if note is not None:
        asset["disagreementNote"] = note
    return asset


def compute_watchlist(conn: duckdb.DuckDBPyConnection | None) -> list[dict[str, Any]] | None:
    """Live analog watchlist, or None to fall back to representative data."""
    if conn is None:
        return None
    try:
        latest = conn.execute("SELECT max(effective_date) FROM features_pit").fetchone()
    except Exception:
        return None
    if not latest or latest[0] is None:
        return None
    key = str(latest[0])

    with _LOCK:
        if _cache["key"] == key and _cache["value"] is not None:
            return _cache["value"]

        ms_engine, state_map, current_state = _market_state_path(conn)
        assets: list[dict[str, Any]] = []
        for ticker, sector in _WATCHLIST:
            try:
                a = _asset(conn, ticker, sector, ms_engine, state_map, current_state)
            except Exception:
                a = None
            if a is not None:
                assets.append(a)

        if not assets:
            return None
        _cache["key"] = key
        _cache["value"] = assets
        return assets
