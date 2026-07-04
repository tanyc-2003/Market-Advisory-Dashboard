"""Feature ingestion against an existing DuckDB connection.

The API holds a single shared read-write connection (DuckDB rejects a second),
so the dynamic-watchlist add path cannot open its own ``FeatureStore``. These
helpers write ``features_pit`` rows through a caller-supplied connection,
mirroring ``FeatureStore.write_features`` exactly (same enrich + arrow insert).
"""
from __future__ import annotations

from typing import Any

import polars as pl

from .features import compute_ohlcv_features, ohlcv_pit_rows

_REQUIRED = {"ticker", "effective_date", "knowledge_date", "feature_name", "feature_value"}


def write_features_conn(conn: Any, df: pl.DataFrame, source: str, version: str) -> int:
    """Append ``df`` into ``features_pit`` via ``conn``; returns rows written.

    Same contract as ``FeatureStore.write_features`` but against an existing
    connection instead of one the store owns.
    """
    missing = _REQUIRED - set(df.columns)
    if missing:
        raise ValueError(f"write_features_conn missing columns: {sorted(missing)}")
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
    conn.register("__incoming__", enriched.to_arrow())
    try:
        conn.execute("INSERT INTO features_pit SELECT * FROM __incoming__")
    finally:
        conn.unregister("__incoming__")
    return enriched.height


def write_equity_ohlcv_conn(conn: Any, ohlcv: pl.DataFrame, ticker: str) -> int:
    """Persist one ticker's OHLCV as engineered features + the ``px_*`` archive.

    Idempotent per ticker: existing ``yfinance`` rows for ``ticker`` are wiped
    first, so a re-add refreshes rather than duplicates. Returns the number of
    engineered feature rows written (0 if the frame is empty).
    """
    if ohlcv is None or ohlcv.is_empty():
        return 0
    conn.execute("DELETE FROM features_pit WHERE ticker = ? AND source = 'yfinance'", [ticker])
    n = write_features_conn(conn, compute_ohlcv_features(ohlcv), source="yfinance", version="v1")
    write_features_conn(conn, ohlcv_pit_rows(ohlcv), source="yfinance", version="v1")
    return n
