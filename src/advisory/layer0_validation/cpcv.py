"""Combinatorial Purged Cross-Validation (Lopez de Prado, 2018).

Each path is the held-out group's score after **purging** training rows
whose forward-return label window overlaps the held-out fold and
applying a 504-day embargo around the test boundaries.  The 504-day
embargo is anchored to the longest model lookback (tail betas).
"""
from __future__ import annotations

from itertools import combinations
from typing import Any, Callable

import numpy as np
import polars as pl
import structlog

from .audit_log import AuditLog
from .walk_forward import WalkForwardCV, _annualised_sharpe

logger = structlog.get_logger(__name__)


SignalFn = Callable[[pl.DataFrame, pl.DataFrame], np.ndarray]


class CPCVRunner:
    """Combinatorial purged CV with embargo.

    Parameters
    ----------
    audit_log:
        Audit log; ``record`` is called once per ``run`` invocation.
    n_groups:
        Number of folds the timeline is divided into.
    n_test_groups:
        How many folds are jointly held out per path.
    embargo_days:
        Calendar-day embargo around each test fold.  Floor is 504 (the
        longest lookback used elsewhere in the system: tail betas).
    horizon_days:
        Forward-return label window.  Training rows within ``horizon_days``
        of a test fold are *purged*.
    cpcv_fallback:
        Either ``"walk_forward"`` or ``None``.
    """

    EMBARGO_FLOOR: int = 504

    def __init__(
        self,
        audit_log: AuditLog,
        n_groups: int = 6,
        n_test_groups: int = 2,
        embargo_days: int = 504,
        horizon_days: int = 10,
        cpcv_fallback: str | None = "walk_forward",
    ) -> None:
        if embargo_days < self.EMBARGO_FLOOR:
            raise ValueError(
                f"embargo_days={embargo_days} below floor {self.EMBARGO_FLOOR}"
            )
        if n_test_groups < 1 or n_test_groups >= n_groups:
            raise ValueError("n_test_groups must satisfy 1 <= n_test_groups < n_groups")
        self.audit_log = audit_log
        self.n_groups = n_groups
        self.n_test_groups = n_test_groups
        self.embargo_days = embargo_days
        self.horizon_days = horizon_days
        self.cpcv_fallback = cpcv_fallback

    def _build_groups(self, n_rows: int) -> list[range]:
        size = n_rows // self.n_groups
        groups: list[range] = []
        for g in range(self.n_groups):
            start = g * size
            end = (g + 1) * size if g < self.n_groups - 1 else n_rows
            groups.append(range(start, end))
        return groups

    def _score_one_path(
        self,
        feature_history: pl.DataFrame,
        groups: list[range],
        test_group_ids: tuple[int, ...],
        signal_fn: SignalFn,
    ) -> float:
        n = feature_history.height
        test_idx: set[int] = set()
        for g in test_group_ids:
            test_idx.update(groups[g])

        # Embargo + purge around the test fold edges
        forbidden = set(test_idx)
        for g in test_group_ids:
            start, stop = groups[g].start, groups[g].stop
            for k in range(max(0, start - self.embargo_days), start):
                forbidden.add(k)
            for k in range(stop, min(n, stop + self.embargo_days)):
                forbidden.add(k)
            for k in range(max(0, start - self.horizon_days), start):
                forbidden.add(k)
            for k in range(stop, min(n, stop + self.horizon_days)):
                forbidden.add(k)

        train_idx = sorted(set(range(n)) - forbidden)
        test_idx_sorted = sorted(test_idx)
        if len(train_idx) < 30 or len(test_idx_sorted) < 5:
            return float("nan")

        train_df = feature_history[train_idx]
        test_df = feature_history[test_idx_sorted]
        try:
            signal = signal_fn(train_df, test_df)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("cpcv_signal_fn_error", error=str(exc))
            return float("nan")
        return _annualised_sharpe(np.asarray(signal, dtype=float))

    def run(
        self,
        feature_history: pl.DataFrame,
        signal_fn: SignalFn,
    ) -> dict[str, Any]:
        # Record before computing so a crash mid-run still costs a trial.
        self.audit_log.record(
            "layer0",
            "cpcv_run",
            {
                "n_groups": self.n_groups,
                "n_test_groups": self.n_test_groups,
                "embargo_days": self.embargo_days,
                "horizon_days": self.horizon_days,
            },
        )

        n = feature_history.height
        min_required = self.n_groups * (self.embargo_days + 50)
        if n < min_required:
            logger.warning(
                "cpcv_insufficient_data",
                n_rows=n,
                min_required=min_required,
                fallback=self.cpcv_fallback,
            )
            if self.cpcv_fallback == "walk_forward":
                wf = WalkForwardCV(self.audit_log, embargo_days=self.embargo_days)
                wf_result = wf.run(feature_history, signal_fn)
                wf_result["fallback"] = "walk_forward"
                return wf_result
            return {
                "sharpes": [],
                "p30": 0.0,
                "p50": 0.0,
                "n_paths": 0,
                "status": "INSUFFICIENT_DATA",
            }

        groups = self._build_groups(n)
        paths = list(combinations(range(self.n_groups), self.n_test_groups))
        sharpes: list[float] = []
        for path in paths:
            sharpe = self._score_one_path(feature_history, groups, path, signal_fn)
            if np.isfinite(sharpe):
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
