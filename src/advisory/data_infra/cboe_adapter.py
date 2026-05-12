"""CBOE put/call ratio adapter.

CBOE publishes a daily CSV containing the equity, index, and total
put/call ratios.  The V7_lite options-proxy dimension consumes the
**total** ratio.  Results are cached to the ``cboe_pc_ratio`` DuckDB
table so dashboard renders never trigger a fresh web request.
"""
from __future__ import annotations

import io
from datetime import date
from typing import Any

import duckdb
import pandas as pd
import structlog

logger = structlog.get_logger(__name__)


CBOE_PC_URL = (
    "https://cdn.cboe.com/api/global/us_indices/daily_prices/"
    "VOL_history.csv"
)
"""Best-effort CSV endpoint for the daily P/C ratio.

CBOE periodically reshuffles its public download paths.  When this URL
breaks the operator can populate ``cboe_pc_ratio`` manually from the
free CBOE downloads page; the adapter reads from the table only.
"""


class CBOEAdapter:
    """Fetches and caches the CBOE total put/call ratio."""

    def __init__(
        self,
        conn: duckdb.DuckDBPyConnection,
        http_client: Any | None = None,
    ) -> None:
        self.conn = conn
        self.http_client = http_client

    def fetch_put_call_ratio(self, as_of_date: date) -> float | None:
        """Return the cached ratio for ``as_of_date``, or ``None`` if
        not available (weekends, holidays, pre-data).
        """
        row = self.conn.execute(
            "SELECT ratio FROM cboe_pc_ratio WHERE pc_date = ?",
            (as_of_date.isoformat(),),
        ).fetchone()
        return float(row[0]) if row else None

    def write_rows(self, rows: list[tuple[date, float]]) -> int:
        """Idempotently upsert ``(date, ratio)`` rows into the cache.

        Used by both the real downloader and by tests/manual loaders.
        """
        if not rows:
            return 0
        for d, r in rows:
            self.conn.execute(
                "INSERT OR REPLACE INTO cboe_pc_ratio (pc_date, ratio) VALUES (?, ?)",
                (d.isoformat(), float(r)),
            )
        return len(rows)

    def download_and_cache(self) -> int:
        """Download the CBOE CSV and cache parsed rows.  Returns the
        number of rows written.  Best-effort: returns 0 if the endpoint
        is unreachable or the CSV layout has changed.
        """
        client = self.http_client
        try:
            if client is None:
                import requests as _r

                resp = _r.get(CBOE_PC_URL, timeout=30)
                payload = resp.content
            else:
                resp = client.get(CBOE_PC_URL, timeout=30)
                payload = resp.content if hasattr(resp, "content") else resp.text.encode()
        except Exception as exc:  # pragma: no cover - network path
            logger.warning("cboe_download_failed", error=str(exc))
            return 0

        try:
            df = pd.read_csv(io.BytesIO(payload))
        except Exception as exc:  # pragma: no cover - parse path
            logger.warning("cboe_parse_failed", error=str(exc))
            return 0

        # CBOE CSV layouts vary.  Try a couple of common column shapes.
        date_col = next(
            (c for c in df.columns if c.lower() in ("date", "trading day", "tradingday")),
            None,
        )
        ratio_col = next(
            (
                c
                for c in df.columns
                if c.lower().replace(" ", "").replace("_", "") in (
                    "totalputcall", "totalputcallratio", "putcallratio",
                )
            ),
            None,
        )
        if date_col is None or ratio_col is None:
            logger.warning(
                "cboe_csv_layout_unknown",
                columns=list(df.columns),
            )
            return 0

        df = df[[date_col, ratio_col]].dropna()
        df[date_col] = pd.to_datetime(df[date_col]).dt.date
        df[ratio_col] = pd.to_numeric(df[ratio_col], errors="coerce")
        df = df.dropna(subset=[ratio_col])

        rows: list[tuple[date, float]] = [
            (d, float(r)) for d, r in zip(df[date_col], df[ratio_col])
        ]
        return self.write_rows(rows)
