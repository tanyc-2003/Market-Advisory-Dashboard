"""V7_lite Phase 1: YFinanceAdapter validation + audit (no network)."""
from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock

import duckdb
import polars as pl
import pytest

from src.advisory.data_infra.schema import bootstrap_schema
from src.advisory.data_infra.yfinance_adapter import (
    MAX_CONSEC_GAPS,
    YFinanceAdapter,
)


def _ohlcv(ticker: str, dates: list[date]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "ticker": [ticker] * len(dates),
            "effective_date": dates,
            "open": [100.0] * len(dates),
            "high": [101.0] * len(dates),
            "low": [99.0] * len(dates),
            "close": [100.5] * len(dates),
            "volume": [1_000_000.0] * len(dates),
        }
    )


@pytest.fixture
def adapter():
    conn = duckdb.connect(":memory:")
    bootstrap_schema(conn)
    connector = MagicMock()
    return YFinanceAdapter(audit_conn=conn, connector=connector, sleep_fn=lambda _s: None)


def test_returns_polars_dataframe_with_correct_schema(adapter):
    dates = [date(2024, 1, i + 1) for i in range(5)]
    adapter.connector.fetch_daily_ohlcv.return_value = _ohlcv("SPY", dates)
    out = adapter.fetch_ohlcv(["SPY"], date(2024, 1, 1), date(2024, 1, 31))
    assert {"ticker", "open", "high", "low", "close", "volume"}.issubset(set(out.columns))
    assert out.height == 5


def test_bad_rows_dropped_and_audit_status_BAD_ROWS(adapter):
    dates = [date(2024, 1, i + 1) for i in range(5)]
    df = _ohlcv("SPY", dates).with_columns(
        pl.when(pl.col("effective_date") == date(2024, 1, 3))
        .then(pl.lit(50.0))
        .otherwise(pl.col("high"))
        .alias("high")
    )
    adapter.connector.fetch_daily_ohlcv.return_value = df
    out = adapter.fetch_ohlcv(["SPY"], date(2024, 1, 1), date(2024, 1, 31))
    # Bad row dropped — only 4 remain.
    assert out.height == 4
    audit = adapter.read_audit()
    assert any(r == "BAD_ROWS" for r in audit["status"].to_list())


def test_missing_ticker_logged_not_raised(adapter):
    adapter.connector.fetch_daily_ohlcv.return_value = _ohlcv("SPY", [date(2024, 1, 1)])
    out = adapter.fetch_ohlcv(["SPY", "DOESNOTEXIST"], date(2024, 1, 1), date(2024, 1, 5))
    assert out.height == 1
    audit = adapter.read_audit()
    statuses = audit["status"].to_list()
    assert "MISSING" in statuses


def test_retry_on_exception(adapter):
    dates = [date(2024, 1, i + 1) for i in range(3)]
    adapter.connector.fetch_daily_ohlcv.side_effect = [
        RuntimeError("boom"),
        _ohlcv("SPY", dates),
    ]
    out = adapter.fetch_ohlcv(["SPY"], date(2024, 1, 1), date(2024, 1, 31))
    assert out.height == 3
    assert adapter.connector.fetch_daily_ohlcv.call_count == 2


def test_gap_detection_flags_long_gap(adapter):
    base = date(2024, 1, 1)
    # 4 days then big gap (~14 days) repeated 4 times -> several consecutive
    # > 3-calendar-day gaps.
    dates = [base + timedelta(days=k) for k in (0, 14, 28, 42, 56)]
    adapter.connector.fetch_daily_ohlcv.return_value = _ohlcv("SPY", dates)
    adapter.fetch_ohlcv(["SPY"], base, base + timedelta(days=60))
    audit = adapter.read_audit()
    assert any(s == "GAP_WARNING" for s in audit["status"].to_list())


def test_no_gap_warning_within_threshold(adapter):
    dates = [date(2024, 1, i + 1) for i in range(20)]
    adapter.connector.fetch_daily_ohlcv.return_value = _ohlcv("SPY", dates)
    adapter.fetch_ohlcv(["SPY"], date(2024, 1, 1), date(2024, 1, 31))
    audit = adapter.read_audit()
    assert all(s != "GAP_WARNING" for s in audit["status"].to_list())
