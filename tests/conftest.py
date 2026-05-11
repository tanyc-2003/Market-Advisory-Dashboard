"""Shared fixtures: in-memory DuckDB stores and synthetic feature frames."""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import polars as pl
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.advisory.data_infra.feature_store import FeatureStore  # noqa: E402
from src.advisory.layer0_validation.audit_log import AuditLog  # noqa: E402


def _business_days(end: date, n: int) -> list[date]:
    out: list[date] = []
    cursor = end
    while len(out) < n:
        if cursor.weekday() < 5:
            out.append(cursor)
        cursor -= timedelta(days=1)
    return list(reversed(out))


@pytest.fixture
def audit_log() -> AuditLog:
    log = AuditLog(":memory:")
    yield log
    log.close()


@pytest.fixture
def feature_store(tmp_path: Path) -> FeatureStore:
    cache = tmp_path / "cache"
    cache.mkdir()
    db_path = tmp_path / "fs.duckdb"
    store = FeatureStore(db_path, cache)
    yield store
    store.close()


@pytest.fixture
def synthetic_feature_history() -> pl.DataFrame:
    """A small Polars frame with the columns the engines need."""
    rng = np.random.default_rng(42)
    dates = _business_days(date(2024, 12, 31), 800)
    ret_1d = rng.normal(0.0005, 0.012, size=len(dates))
    vol = (
        pl.Series(ret_1d)
        .rolling_std(window_size=21, min_periods=1)
        .fill_null(0.012)
        .to_numpy()
        * float(np.sqrt(252))
    )
    cum = np.cumprod(1.0 + ret_1d)
    ret_21d = np.concatenate([np.zeros(21), cum[21:] / cum[:-21] - 1.0])
    fwd = np.concatenate([cum[10:] / cum[:-10] - 1.0, np.zeros(10)])
    df = pl.DataFrame(
        {
            "effective_date": dates,
            "ret_1d": ret_1d,
            "ret_21d": ret_21d,
            "realized_vol_21d": vol,
            "vix_percentile_63d": rng.uniform(0.0, 1.0, len(dates)),
            "hy_spread_roc_21d": rng.normal(0.0, 0.05, len(dates)),
            "yield_curve_slope": rng.normal(0.5, 0.3, len(dates)),
            "pct_above_ma50": rng.uniform(0.0, 1.0, len(dates)),
            "ret_fwd_10d": fwd,
            "hmm_state": rng.integers(0, 3, len(dates)),
        }
    )
    return df


@pytest.fixture
def feature_cols() -> list[str]:
    return [
        "ret_1d",
        "ret_21d",
        "realized_vol_21d",
        "vix_percentile_63d",
        "hy_spread_roc_21d",
        "yield_curve_slope",
        "pct_above_ma50",
    ]
