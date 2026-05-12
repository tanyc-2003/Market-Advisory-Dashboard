"""V7_lite yfinance adapter.

Wraps :class:`YFinanceConnector` with the data-quality machinery V7_lite
requires:

* **OHLCV sanity checks** — drop rows where ``high < low``, ``close > high``,
  or ``close < low``, with a logged warning per bad row.
* **Consecutive-gap detection** — counts intervals between consecutive
  trading days that exceed 3 calendar days; logs a warning above
  :data:`MAX_CONSEC_GAPS`.
* **Retry with exponential backoff** — :data:`MAX_RETRIES` attempts, base
  delay :data:`RETRY_BACKOFF_S`.
* **Audit log** — every per-ticker fetch outcome lands in the
  ``yfinance_fetch_audit`` DuckDB table.  This is the table read by
  :meth:`ContinuousValidator._data_integrity_check` to decide whether
  to pause the validation clock.

In :func:`fetch_sector_etfs` the 11 sector ETFs (XLK/XLF/XLV/XLY/XLP/
XLE/XLI/XLB/XLRE/XLU/XLC) are fetched in a single call.  They are
**not** part of the 100-ticker analytical universe — they back the
``sector_relative_ret_252d`` feature in :mod:`feature_pipeline_lite`.
"""
from __future__ import annotations

import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import duckdb
import polars as pl
import structlog

from .ingestion import YFinanceConnector

logger = structlog.get_logger(__name__)


MAX_RETRIES: int = 3
RETRY_BACKOFF_S: int = 5
MAX_CONSEC_GAPS: int = 3
"""Architecturally-pinned thresholds; renaming them is a controlled change."""


SECTOR_ETFS: tuple[str, ...] = (
    "XLK", "XLF", "XLV", "XLY", "XLP", "XLE",
    "XLI", "XLB", "XLRE", "XLU", "XLC",
)


VIX_TICKERS: dict[str, str] = {
    "vix_9d": "^VIX9D",
    "vix_3m": "^VIX3M",
    "skew_index": "^SKEW",
}


_OHLCV_SCHEMA = {
    "ticker": pl.Utf8,
    "effective_date": pl.Date,
    "open": pl.Float64,
    "high": pl.Float64,
    "low": pl.Float64,
    "close": pl.Float64,
    "volume": pl.Float64,
}


class YFinanceAdapter:
    """V7_lite-grade yfinance fetcher with validation, retry, and audit.

    Parameters
    ----------
    audit_conn:
        DuckDB connection to the *main* database (where
        ``yfinance_fetch_audit`` lives).  Pass an in-memory connection
        for tests.
    connector:
        Optional injected :class:`YFinanceConnector` (for tests that
        want to stub the network call).
    """

    def __init__(
        self,
        audit_conn: duckdb.DuckDBPyConnection,
        connector: YFinanceConnector | None = None,
        sleep_fn=time.sleep,
    ) -> None:
        self.conn = audit_conn
        self.connector = connector or YFinanceConnector()
        self._sleep = sleep_fn

    # --- public surface ---------------------------------------------------

    def fetch_ohlcv(
        self,
        tickers: list[str],
        start: date,
        end: date,
        auto_adjust: bool = False,
    ) -> pl.DataFrame:
        """Fetch + validate + audit daily OHLCV for the given tickers.

        ``auto_adjust`` defaults to **False**.  Setting it to True is
        permitted but logged loudly — adjusted prices change retroactively
        and corrupt the bitemporal store.
        """
        if auto_adjust:
            logger.warning(
                "yfinance_auto_adjust_true_use_with_care",
                rationale="adjusted prices change retroactively; corrupts bitemporal store",
            )

        last_exc: Exception | None = None
        raw = pl.DataFrame(schema=_OHLCV_SCHEMA)
        for attempt in range(MAX_RETRIES):
            try:
                raw = self.connector.fetch_daily_ohlcv(tickers, start, end)
                last_exc = None
                break
            except Exception as exc:  # pragma: no cover - exercised by tests
                last_exc = exc
                delay = RETRY_BACKOFF_S * (2 ** attempt)
                logger.warning(
                    "yfinance_fetch_retry",
                    attempt=attempt + 1,
                    error=str(exc),
                    delay_s=delay,
                )
                self._sleep(delay)
        if last_exc is not None:
            logger.warning("yfinance_fetch_failed_after_retries", error=str(last_exc))
            for t in tickers:
                self._record_audit(t, status="MISSING", n_rows=0, note=str(last_exc))
            return raw

        return self._validate_and_reshape(raw, tickers, start)

    def fetch_sector_etfs(self, start: date, end: date) -> pl.DataFrame:
        """Daily OHLCV for the 11 sector ETFs (fetched in one call)."""
        return self.fetch_ohlcv(list(SECTOR_ETFS), start, end)

    def fetch_vix_term_structure(
        self, start: date, end: date
    ) -> pl.DataFrame:
        """Fetch ^VIX9D, ^VIX3M, ^SKEW.

        VIXCLS (1M VIX) comes from FRED via
        :func:`~src.advisory.data_infra.fred_adapter.fetch_fred_pit_safe`.
        """
        return self.fetch_ohlcv(list(VIX_TICKERS.values()), start, end)

    # --- validation + audit ----------------------------------------------

    def _validate_and_reshape(
        self,
        raw: pl.DataFrame,
        requested_tickers: list[str],
        fetch_date: date,
    ) -> pl.DataFrame:
        if raw.is_empty():
            for t in requested_tickers:
                self._record_audit(
                    t, status="MISSING", n_rows=0, fetch_date=fetch_date,
                    note="empty response",
                )
            return raw

        out_frames: list[pl.DataFrame] = []
        present = set(raw["ticker"].unique().to_list())
        for t in requested_tickers:
            if t not in present:
                self._record_audit(
                    t, status="MISSING", n_rows=0, fetch_date=fetch_date,
                    note="ticker not in response",
                )
                continue

            sub = raw.filter(pl.col("ticker") == t).sort("effective_date")
            n_before = sub.height

            # OHLCV sanity check
            bad_mask = (
                (pl.col("high") < pl.col("low"))
                | (pl.col("close") > pl.col("high"))
                | (pl.col("close") < pl.col("low"))
            )
            bad = sub.filter(bad_mask)
            if bad.height:
                for row in bad.iter_rows(named=True):
                    logger.warning(
                        "yfinance_bad_row",
                        ticker=t,
                        date=str(row["effective_date"]),
                        ohlc=(row["open"], row["high"], row["low"], row["close"]),
                    )
            sub = sub.filter(~bad_mask)

            n_consec_gaps = self._count_consecutive_gaps(sub)
            status = "OK"
            note: str | None = None
            if bad.height:
                status = "BAD_ROWS"
                note = f"{bad.height} OHLCV-inconsistent rows dropped"
            if n_consec_gaps > MAX_CONSEC_GAPS:
                status = "GAP_WARNING"
                note = (
                    f"{n_consec_gaps} consecutive trading-day gaps "
                    f"> {MAX_CONSEC_GAPS}"
                )
                logger.warning(
                    "yfinance_gap_warning",
                    ticker=t,
                    n_consec_gaps=n_consec_gaps,
                )

            self._record_audit(
                t,
                status=status,
                n_rows=sub.height,
                n_bad_rows=bad.height,
                n_consec_gaps=n_consec_gaps,
                fetch_date=fetch_date,
                note=note,
            )
            out_frames.append(sub)

        if not out_frames:
            return pl.DataFrame(schema=_OHLCV_SCHEMA)
        return pl.concat(out_frames)

    @staticmethod
    def _count_consecutive_gaps(sub: pl.DataFrame) -> int:
        """Number of consecutive intervals between trading days that exceed
        3 calendar days.  Weekends are ignored: a Mon→Fri interval is 3
        calendar days, not a gap.
        """
        dates = sub["effective_date"].to_list()
        if len(dates) < 2:
            return 0
        gap = 0
        streak = 0
        for prev, curr in zip(dates[:-1], dates[1:]):
            delta = (curr - prev).days
            if delta > 3:
                streak += 1
                gap = max(gap, streak)
            else:
                streak = 0
        return gap

    # --- audit log helpers ------------------------------------------------

    def _record_audit(
        self,
        ticker: str,
        status: str,
        n_rows: int,
        n_bad_rows: int = 0,
        n_consec_gaps: int = 0,
        fetch_date: date | None = None,
        note: str | None = None,
        app_mode: str = "v7_lite",
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO yfinance_fetch_audit
                (ticker, fetch_date, status, n_rows, n_bad_rows,
                 n_consec_gaps, note, app_mode)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ticker,
                fetch_date.isoformat() if fetch_date else None,
                status,
                int(n_rows),
                int(n_bad_rows),
                int(n_consec_gaps),
                note,
                app_mode,
            ),
        )

    def read_audit(
        self,
        since: date | None = None,
        tickers: list[str] | None = None,
    ) -> pl.DataFrame:
        """Return recent audit rows as a Polars DataFrame.

        Used by :meth:`ContinuousValidator._data_integrity_check`.
        """
        where: list[str] = []
        params: list[Any] = []
        if since is not None:
            where.append("fetched_at >= ?")
            params.append(since.isoformat())
        if tickers:
            where.append("ticker = ANY(?)")
            params.append(tickers)
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        rows = self.conn.execute(
            f"""
            SELECT ticker, fetch_date, status, n_rows, n_bad_rows,
                   n_consec_gaps, note, app_mode
            FROM yfinance_fetch_audit
            {clause}
            ORDER BY fetched_at DESC
            """,
            params if params else (),
        ).fetchall()
        if not rows:
            return pl.DataFrame(
                schema={
                    "ticker": pl.Utf8,
                    "fetch_date": pl.Date,
                    "status": pl.Utf8,
                    "n_rows": pl.Int64,
                    "n_bad_rows": pl.Int64,
                    "n_consec_gaps": pl.Int64,
                    "note": pl.Utf8,
                    "app_mode": pl.Utf8,
                }
            )
        return pl.DataFrame(
            {
                "ticker": [r[0] for r in rows],
                "fetch_date": [r[1] for r in rows],
                "status": [r[2] for r in rows],
                "n_rows": [int(r[3]) if r[3] is not None else 0 for r in rows],
                "n_bad_rows": [int(r[4]) if r[4] is not None else 0 for r in rows],
                "n_consec_gaps": [int(r[5]) if r[5] is not None else 0 for r in rows],
                "note": [r[6] for r in rows],
                "app_mode": [r[7] for r in rows],
            }
        )
