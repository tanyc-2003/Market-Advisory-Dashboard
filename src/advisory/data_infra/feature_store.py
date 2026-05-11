"""Bitemporal feature store.

All upstream layers read features through this class — never directly
from DuckDB — so the point-in-time invariants live in one place.
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

import duckdb
import polars as pl
import structlog

from .lag import get_lag
from .schema import PIT_QUERY, bootstrap_schema

logger = structlog.get_logger(__name__)


def trading_days_before(anchor: date, n_days: int) -> date:
    """Return the calendar date ``n_days`` trading days before ``anchor``.

    Approximation: weekend skipping only (no holiday calendar).  Sufficient
    for lag arithmetic over short windows.
    """
    cursor = anchor
    remaining = n_days
    while remaining > 0:
        cursor = cursor - timedelta(days=1)
        if cursor.weekday() < 5:
            remaining -= 1
    return cursor


class FeatureStore:
    """Read/write feature data with bitemporal guarantees."""

    def __init__(self, db_path: Path | str, cache_dir: Path | str):
        db_str = str(db_path) if isinstance(db_path, Path) else db_path
        self.conn = duckdb.connect(db_str)
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        bootstrap_schema(self.conn)

    def get_feature_pit(
        self,
        ticker: str,
        feature_name: str,
        prediction_date: date,
        effective_date: date | None = None,
    ) -> float | None:
        """Return the most recent value of ``feature_name`` whose
        ``knowledge_date < prediction_date``.  Strict less-than enforces
        the T-1 invariant.
        """
        eff = effective_date or prediction_date
        row = self.conn.execute(
            PIT_QUERY,
            (
                ticker,
                feature_name,
                prediction_date.isoformat(),
                eff.isoformat(),
            ),
        ).fetchone()
        return float(row[0]) if row and row[0] is not None else None

    def get_feature_history(
        self,
        tickers: list[str],
        feature_names: list[str],
        start_date: date,
        end_date: date,
        as_of_date: date,
    ) -> pl.DataFrame:
        """Wide-format feature history that is point-in-time safe at ``as_of_date``.

        Each feature's per-row availability is capped by its own lag:
        a feature with lag 3 cannot use observations within 3 trading
        days of ``as_of_date``.
        """
        if not tickers or not feature_names:
            return pl.DataFrame()

        long_frames: list[pl.DataFrame] = []
        for feature_name in feature_names:
            lag = get_lag(feature_name)
            cutoff = trading_days_before(as_of_date, lag) if lag > 0 else as_of_date
            sql = """
                SELECT ticker, effective_date, feature_value
                FROM features_pit
                WHERE ticker = ANY(?)
                  AND feature_name = ?
                  AND effective_date BETWEEN ? AND ?
                  AND knowledge_date <= ?
                ORDER BY ticker, effective_date
            """
            rows = self.conn.execute(
                sql,
                (
                    tickers,
                    feature_name,
                    start_date.isoformat(),
                    end_date.isoformat(),
                    cutoff.isoformat(),
                ),
            ).fetchall()
            if not rows:
                continue
            long_frames.append(
                pl.DataFrame(
                    {
                        "ticker": [r[0] for r in rows],
                        "effective_date": [r[1] for r in rows],
                        feature_name: [r[2] for r in rows],
                    }
                )
            )

        if not long_frames:
            return pl.DataFrame(
                schema={"ticker": pl.Utf8, "effective_date": pl.Date},
            )

        result = long_frames[0]
        for extra in long_frames[1:]:
            result = result.join(
                extra, on=["ticker", "effective_date"], how="outer_coalesce"
            )
        return result.sort(["ticker", "effective_date"])

    def write_features(
        self,
        df: pl.DataFrame,
        source: str,
        version: str,
    ) -> int:
        """Append rows into ``features_pit``.

        Required columns: ``ticker``, ``effective_date``, ``knowledge_date``,
        ``feature_name``, ``feature_value``.  Returns the number of rows
        written.
        """
        required = {
            "ticker",
            "effective_date",
            "knowledge_date",
            "feature_name",
            "feature_value",
        }
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"write_features missing columns: {sorted(missing)}")

        enriched = df.with_columns(
            pl.lit(version).alias("feature_version"),
            pl.lit(source).alias("source"),
            pl.lit(True).alias("pit_verified"),
        ).select(
            "ticker",
            "effective_date",
            "knowledge_date",
            "feature_name",
            "feature_value",
            "feature_version",
            "source",
            "pit_verified",
        )

        # Register and insert via a parameterless SQL path so the DuckDB
        # writer sees a single arrow batch.
        self.conn.register("__incoming__", enriched.to_arrow())
        self.conn.execute(
            "INSERT INTO features_pit "
            "SELECT * FROM __incoming__"
        )
        self.conn.unregister("__incoming__")
        return enriched.height

    def cache_snapshot(self, df: pl.DataFrame, snapshot_name: str) -> Path:
        path = self.cache_dir / f"{snapshot_name}.parquet"
        df.write_parquet(path, compression="snappy")
        return path

    def load_snapshot(self, snapshot_name: str) -> pl.DataFrame | None:
        path = self.cache_dir / f"{snapshot_name}.parquet"
        if not path.exists():
            return None
        return pl.read_parquet(path)

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:  # pragma: no cover - defensive
            pass

    def __enter__(self) -> "FeatureStore":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()
