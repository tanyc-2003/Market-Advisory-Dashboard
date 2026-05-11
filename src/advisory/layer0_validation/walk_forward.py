"""Walk-forward CV (expanding window).  CPCV fallback when history is short."""
from __future__ import annotations

from typing import Any, Callable

import numpy as np
import polars as pl
import structlog

from .audit_log import AuditLog

logger = structlog.get_logger(__name__)

ANNUALISATION_FACTOR = float(np.sqrt(252))


def _annualised_sharpe(returns: np.ndarray) -> float:
    if len(returns) < 2:
        return 0.0
    mu = float(np.nanmean(returns))
    sd = float(np.nanstd(returns, ddof=1))
    if sd == 0 or not np.isfinite(sd):
        return 0.0
    return (mu / sd) * ANNUALISATION_FACTOR


class WalkForwardCV:
    """Strict expanding-window walk-forward CV.

    Returns the same shape as :class:`CPCVRunner` so callers can consume
    either uniformly.
    """

    def __init__(self, audit_log: AuditLog, embargo_days: int = 504) -> None:
        if embargo_days < 504:
            raise ValueError("embargo_days must be >= 504 (longest model lookback)")
        self.audit_log = audit_log
        self.embargo_days = embargo_days

    def run(
        self,
        feature_history: pl.DataFrame,
        signal_fn: Callable[[pl.DataFrame, pl.DataFrame], np.ndarray],
        n_splits: int = 5,
        embargo_days: int | None = None,
    ) -> dict[str, Any]:
        embargo = embargo_days if embargo_days is not None else self.embargo_days
        self.audit_log.record(
            "layer0",
            "walk_forward_cv",
            {"n_splits": n_splits, "embargo_days": embargo},
        )

        n = feature_history.height
        if n < (n_splits + 2):
            logger.warning(
                "walk_forward_insufficient_data", n_rows=n, n_splits=n_splits
            )
            return {
                "sharpes": [],
                "p30": 0.0,
                "p50": 0.0,
                "n_paths": 0,
                "status": "INSUFFICIENT_DATA",
            }

        fold_size = max(1, n // (n_splits + 1))
        sharpes: list[float] = []

        for i in range(1, n_splits + 1):
            train_end = i * fold_size
            test_start = train_end + embargo
            test_end = test_start + fold_size
            if test_end > n:
                break
            train = feature_history.slice(0, train_end)
            test = feature_history.slice(test_start, test_end - test_start)
            try:
                signal = signal_fn(train, test)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("walk_forward_signal_fn_error", error=str(exc))
                continue
            sharpe = _annualised_sharpe(np.asarray(signal, dtype=float))
            sharpes.append(sharpe)

        if not sharpes:
            return {
                "sharpes": [],
                "p30": 0.0,
                "p50": 0.0,
                "n_paths": 0,
                "status": "NO_VALID_PATHS",
            }

        arr = np.asarray(sharpes, dtype=float)
        return {
            "sharpes": sharpes,
            "p30": float(np.percentile(arr, 30)),
            "p50": float(np.percentile(arr, 50)),
            "n_paths": len(sharpes),
            "status": "OK",
        }
