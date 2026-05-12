"""HMM model registry helpers.

The ``hmm_model_registry`` DuckDB table is the system's record of which
HMM artifact is currently in production for each ``app_mode``.  Two
operations:

* :func:`register_candidate` — written by the training script after
  ``hmm_v7_lite_YYYYMMDD.pkl`` is saved.
* :func:`promote_candidate` — written by the validation script when a
  candidate passes Layer 0 sign-off; retires the previous production
  model and points the canonical path at the candidate file.

The :func:`load_market_state_engine` factory loads the artifact for a
given mode and returns a fully-initialised :class:`MarketStateEngine`.
"""
from __future__ import annotations

import pickle
import shutil
from datetime import date, datetime
from pathlib import Path
from typing import Any

import duckdb
import structlog

from config.settings import settings

from .engine import MarketStateEngine

logger = structlog.get_logger(__name__)


def register_candidate(
    conn: duckdb.DuckDBPyConnection,
    model_id: str,
    app_mode: str,
    artifact_path: Path,
    training_window_start: date,
    training_window_end: date,
    n_dimensions: int,
    k_selected: int,
    oos_log_likelihood: float,
) -> None:
    """Insert a candidate row with ``validation_status='candidate'``."""
    conn.execute(
        """
        INSERT OR REPLACE INTO hmm_model_registry
            (model_id, app_mode, trained_at, training_window_start,
             training_window_end, n_dimensions, k_selected,
             oos_log_likelihood, validation_status, artifact_path)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'candidate', ?)
        """,
        (
            model_id,
            app_mode,
            datetime.utcnow(),
            training_window_start.isoformat(),
            training_window_end.isoformat(),
            int(n_dimensions),
            int(k_selected),
            float(oos_log_likelihood),
            str(artifact_path),
        ),
    )


def promote_candidate(
    conn: duckdb.DuckDBPyConnection,
    model_id: str,
    app_mode: str,
    walk_forward_sharpe: float,
    deflated_sharpe: float,
    canonical_path: Path,
    artifact_path: Path,
    new_status: str = "lite_survivorship",
) -> None:
    """Promote a candidate to production.

    * Retires the previously-active row for the same ``app_mode``.
    * Marks the candidate as active and updates its sign-off metrics.
    * Copies the candidate artifact to ``canonical_path``.
    """
    # Retire the previous active row(s) for this mode.
    conn.execute(
        """
        UPDATE hmm_model_registry
        SET retired_at = ?, retired_reason = 'superseded'
        WHERE app_mode = ?
          AND retired_at IS NULL
          AND model_id <> ?
        """,
        (datetime.utcnow(), app_mode, model_id),
    )
    conn.execute(
        """
        UPDATE hmm_model_registry
        SET validation_status = ?,
            walk_forward_sharpe = ?,
            deflated_sharpe = ?
        WHERE model_id = ?
        """,
        (new_status, float(walk_forward_sharpe), float(deflated_sharpe), model_id),
    )
    canonical_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(artifact_path, canonical_path)
    logger.info(
        "hmm_promoted",
        model_id=model_id,
        app_mode=app_mode,
        canonical_path=str(canonical_path),
    )


def get_active_model(
    conn: duckdb.DuckDBPyConnection, app_mode: str
) -> dict[str, Any] | None:
    """Return the registry row for the current production model in ``app_mode``."""
    row = conn.execute(
        """
        SELECT model_id, trained_at, n_dimensions, k_selected,
               walk_forward_sharpe, deflated_sharpe, validation_status,
               artifact_path
        FROM hmm_model_registry
        WHERE app_mode = ?
          AND retired_at IS NULL
        ORDER BY trained_at DESC
        LIMIT 1
        """,
        (app_mode,),
    ).fetchone()
    if row is None:
        return None
    return {
        "model_id": row[0],
        "trained_at": row[1],
        "n_dimensions": row[2],
        "k_selected": row[3],
        "walk_forward_sharpe": row[4],
        "deflated_sharpe": row[5],
        "validation_status": row[6],
        "artifact_path": row[7],
    }


def load_market_state_engine(
    app_mode: str | None = None,
    settings_obj=None,
) -> MarketStateEngine:
    """Load the canonical HMM artifact for ``app_mode`` and return a
    fully-initialised :class:`MarketStateEngine`.

    The artifact is a pickle dict shaped as::

        {
            "model":              <fitted GaussianHMM>,
            "feature_cols":       [...9 names...],
            "sigma_cap":          4.0,
            "training_mean":      ndarray,   # optional
            "training_std":       ndarray,   # optional
            "training_end_date":  date,
            "k_selected":         int,
            "oos_log_likelihood": float,
            "n_dimensions":       9,
            "app_mode":           "v7_lite",
        }
    """
    s = settings_obj or settings
    mode = app_mode or s.app_mode
    path = s.hmm_model_path if mode == s.app_mode else (
        s.hmm_model_path_lite if mode == "v7_lite" else s.hmm_model_path_institutional
    )
    if not path.exists():
        raise FileNotFoundError(
            f"HMM artifact for {mode} not found at {path}. "
            f"Run scripts/train_hmm.py first."
        )
    with open(path, "rb") as f:
        artifact = pickle.load(f)
    engine = MarketStateEngine(
        hmm_model=artifact["model"],
        feature_cols=list(artifact["feature_cols"]),
        sigma_cap=float(artifact.get("sigma_cap", 4.0)),
    )
    if "training_mean" in artifact and "training_std" in artifact:
        engine.attach_training_moments(
            artifact["training_mean"], artifact["training_std"]
        )
    return engine
