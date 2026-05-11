"""Out-of-sample log-likelihood K selector for the HMM.

Splits ``feature_history`` chronologically into 80% train / 20% test
(strict — no shuffling) and picks the K with the highest test log-likelihood.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import polars as pl
import structlog
from hmmlearn import hmm

from ..layer0_validation.audit_log import AuditLog
from .engine import winsorize

logger = structlog.get_logger(__name__)


def select_k_oos(
    feature_history: pl.DataFrame,
    feature_cols: list[str],
    candidate_ks: list[int],
    audit_log: AuditLog,
    sigma_cap: float = 4.0,
    random_state: int = 42,
) -> dict[str, Any]:
    """Pick the K with the highest out-of-sample HMM log-likelihood."""
    if not candidate_ks:
        raise ValueError("candidate_ks must be non-empty")

    X = feature_history.select(feature_cols).to_numpy()
    n = X.shape[0]
    if n < 50:
        raise ValueError(f"feature_history has only {n} rows; need >= 50")

    split = int(n * 0.8)
    X_train_raw = X[:split]
    X_test_raw = X[split:]
    assert split > 0 and len(X_test_raw) > 0, "train/test split degenerate"

    X_train = winsorize(X_train_raw, sigma_cap)
    X_test = winsorize(X_test_raw, sigma_cap)

    scores: dict[int, float] = {}
    for k in candidate_ks:
        audit_log.record("layer1", "select_k_oos", {"k": k})
        try:
            model = hmm.GaussianHMM(
                n_components=k,
                covariance_type="full",
                n_iter=200,
                random_state=random_state,
            )
            model.fit(X_train)
            ll = float(model.score(X_test))
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("select_k_oos_fit_failed", k=k, error=str(exc))
            ll = float("-inf")
        scores[k] = ll
        logger.debug("select_k_oos_candidate", k=k, oos_ll=ll)

    best_k = max(scores, key=lambda kk: scores[kk])
    return {
        "selected_k": best_k,
        "selection_reason": "out_of_sample_log_likelihood",
        "scores": scores,
        "n_train": len(X_train),
        "n_test": len(X_test),
    }
