"""Live Layer 1 market-state inference for the dashboard.

Loads the trained lite HMM artifact and reports the *current regime* over the
most recent market-average features, in the shape the React market-state panel
expects.

We report **recent regime occupancy** — the share of the last quarter (≈63
trading days) the Viterbi path spent in each state. A full-covariance Gaussian
HMM produces near one-hot point posteriors, so a single-day probability is
uninformative; occupancy is a robust, interpretable "what regime have we been
in, and is today diverging" measure that always carries a real spread.

The HMM emits unlabeled states (0..K-1); we name them along a risk-on↔risk-off
spectrum derived from each state's mean trend (ret_21d) and volatility
(realized_vol_21d), so the labels are always distinct and ordered.

If the canonical (promoted) model is present the result is flagged
``validated``; otherwise the newest candidate is used and a research-preview
``disclosure`` is attached.
"""
from __future__ import annotations

import pickle
import threading
from pathlib import Path
from typing import Any

import duckdb
import numpy as np

from config.settings import settings

_LOCK = threading.Lock()
_engine_cache: dict[str, tuple[Any, bool]] = {}

# Risk-off → risk-on. K labels are spread across this spectrum so they stay
# distinct and ordered regardless of how many states the HMM selected.
_SPECTRUM = ["Stressed Bear", "Calm Bear", "Neutral / transition", "Volatile Bull", "Calm Bull"]

_HISTORY_SQL = """
    SELECT effective_date, feature_name, AVG(feature_value) AS value
    FROM features_pit
    WHERE feature_name IN ({cols})
    GROUP BY effective_date, feature_name
    ORDER BY effective_date
"""


def _find_model_path() -> Path | None:
    """Prefer the promoted canonical model; fall back to the newest candidate."""
    canonical = settings.hmm_model_path_lite
    if canonical.exists():
        return canonical
    models_dir = canonical.parent
    if not models_dir.exists():
        return None
    candidates = sorted(models_dir.glob("hmm_v7_lite_*.pkl"))
    return candidates[-1] if candidates else None


def _load_engine() -> tuple[Any, bool]:
    """Return (engine, validated) or (None, False) when no model is available."""
    path = _find_model_path()
    if path is None:
        return None, False
    key = str(path)
    with _LOCK:
        cached = _engine_cache.get(key)
        if cached is not None:
            return cached
        with open(path, "rb") as fh:
            art = pickle.load(fh)
        from ..layer1_market_state.engine import MarketStateEngine  # lazy: needs hmmlearn

        engine = MarketStateEngine(
            hmm_model=art["model"],
            feature_cols=list(art["feature_cols"]),
            sigma_cap=float(art.get("sigma_cap", 4.0)),
        )
        tm, ts = art.get("training_mean"), art.get("training_std")
        if tm is not None and ts is not None:
            engine.attach_training_moments(np.asarray(tm, dtype=float), np.asarray(ts, dtype=float))
        result = (engine, path == settings.hmm_model_path_lite)
        _engine_cache[key] = result
        return result


def _recent_window(conn: duckdb.DuckDBPyConnection, feature_cols: list[str], limit: int = 300):
    import polars as pl

    cols = ", ".join(f"'{c}'" for c in feature_cols)
    rows = conn.execute(_HISTORY_SQL.format(cols=cols)).fetchall()
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
        .drop_nulls(subset=["value"])
        .pivot(values="value", index="effective_date", on="feature_name")
        .sort("effective_date")
        .drop_nulls()
    )
    if df.height == 0 or any(c not in df.columns for c in feature_cols):
        return None
    return df.tail(limit)


def _zscore(v: np.ndarray) -> np.ndarray:
    sd = float(np.std(v))
    return (v - float(np.mean(v))) / (sd if sd > 0 else 1.0)


def _label_states(means: np.ndarray, feature_cols: list[str]) -> list[str]:
    """Name each state along the risk-on↔risk-off spectrum, ranked by
    standardized (trend − volatility). Always distinct for K ≤ 5."""
    k = means.shape[0]
    idx_trend = feature_cols.index("ret_21d") if "ret_21d" in feature_cols else min(2, means.shape[1] - 1)
    idx_vol = feature_cols.index("realized_vol_21d") if "realized_vol_21d" in feature_cols else min(3, means.shape[1] - 1)
    score = _zscore(means[:, idx_trend]) - _zscore(means[:, idx_vol])  # high = risk-on
    order = np.argsort(score)  # ascending: most risk-off first

    labels = [""] * k
    last = len(_SPECTRUM) - 1
    for rank, state_idx in enumerate(order):
        spec = 0 if k == 1 else round(rank / (k - 1) * last)
        labels[int(state_idx)] = _SPECTRUM[spec]
    return labels


def _recent_occupancy(engine: Any, window, lookback: int = 63) -> tuple[np.ndarray, float, bool, int, int]:
    """Fraction of the last ``lookback`` days the Viterbi path spent in each state.

    Returns (occupancy, uncertainty, transition_flag, current_state, dominant_state).
    """
    path = np.asarray(engine.decode_path(window))
    if path.size == 0:
        raise ValueError("empty Viterbi path")
    recent = path[-lookback:] if path.size > lookback else path
    k = int(np.asarray(engine.hmm_model.means_).shape[0])
    counts = np.bincount(recent, minlength=k).astype(float)
    occ = counts / counts.sum()

    current_idx = int(path[-1])
    dominant_idx = int(np.argmax(occ))
    max_occ = float(occ.max())
    uncertainty = 1.0 - max_occ
    transition = current_idx != dominant_idx or max_occ < 0.5
    return occ, uncertainty, transition, current_idx, dominant_idx


def _candidate_wf_sharpe(conn: duckdb.DuckDBPyConnection) -> float | None:
    try:
        from ..layer0_validation.report import load_latest_report

        rep = load_latest_report(conn, "hmm_candidate")
        return None if rep is None else float(rep.walk_forward_sharpe)
    except Exception:
        return None


def compute_market_state(conn: duckdb.DuckDBPyConnection | None) -> dict[str, Any] | None:
    """Return the live market-state payload, or None to fall back to representative."""
    if conn is None:
        return None
    engine, validated = _load_engine()
    if engine is None:
        return None
    window = _recent_window(conn, engine.feature_cols)
    if window is None or window.height < 5:
        return None
    try:
        occ, uncertainty, transition_signal, current_idx, dominant_idx = _recent_occupancy(engine, window)
        labels = _label_states(np.asarray(engine.hmm_model.means_, dtype=float), engine.feature_cols)
    except Exception:
        return None

    pairs = sorted(
        ({"name": labels[i], "prob": float(occ[i])} for i in range(len(occ))),
        key=lambda d: d["prob"],
        reverse=True,
    )
    dominant_name = labels[dominant_idx]
    current_name = labels[current_idx]
    dominant_share = float(occ[dominant_idx]) * 100

    if validated:
        disclosure = None
    else:
        wf = _candidate_wf_sharpe(conn)
        disclosure = (
            f"Research preview — regime model walk-forward Sharpe {wf:.2f} < 0.50 floor; "
            "shown for situational awareness, not as a validated signal."
            if wf is not None
            else "Research preview — regime model has not passed Layer 0 predictive sign-off; "
            "shown for situational awareness, not as a validated signal."
        )

    if transition_signal:
        transition = (
            f"Regime mix is unsettled — today reads as {current_name}, against a prevailing "
            f"{dominant_name} over the last quarter ({dominant_share:.0f}% of days). "
            "Treat regime persistence as uncertain."
        )
    else:
        transition = (
            f"{dominant_name} has prevailed over the last quarter ({dominant_share:.0f}% of days), "
            "and today is consistent with it."
        )

    return {
        "states": pairs,
        "uncertainty": f"{uncertainty:.2f}",
        "transition": transition,
        "validated": validated,
        "disclosure": disclosure,
        "source": "live",
    }
