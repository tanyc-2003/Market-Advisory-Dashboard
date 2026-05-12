"""Tests for the real data connectors (network-free)."""
from __future__ import annotations

import io
from datetime import date
from unittest.mock import patch

import polars as pl

from src.advisory.data_infra.ingestion import (
    CBOEConnector,
    FREDConnector,
    PolygonConnector,
    SharadarConnector,
    YFinanceConnector,
)


def test_polygon_stub_returns_empty():
    df = PolygonConnector().fetch_daily_ohlcv(["SPY"], date(2024, 1, 1), date(2024, 2, 1))
    assert df.is_empty()


def test_cboe_stub_returns_empty():
    df = CBOEConnector().fetch_options_surface(date(2024, 1, 1))
    assert df.is_empty()


def test_sharadar_stub_returns_empty():
    df = SharadarConnector().fetch_fundamentals(["AAPL"], date(2024, 1, 1), date(2024, 2, 1))
    assert df.is_empty()


def test_fred_parses_csv_payload():
    csv = "observation_date,DGS10\n2024-01-02,3.95\n2024-01-03,3.91\n2024-01-04,.\n"

    class _FakeResp:
        def __init__(self, body: bytes) -> None:
            self._body = body

        def read(self) -> bytes:
            return self._body

        def __enter__(self) -> "_FakeResp":
            return self

        def __exit__(self, *_args, **_kwargs) -> None:
            pass

    with patch(
        "src.advisory.data_infra.ingestion.urllib.request.urlopen",
        return_value=_FakeResp(csv.encode("utf-8")),
    ):
        out = FREDConnector().fetch_series(
            "DGS10", date(2024, 1, 1), date(2024, 1, 5)
        )

    assert out.height == 2  # "." row filtered out
    assert set(out.columns) == {"series_id", "effective_date", "value"}
    assert out["series_id"][0] == "DGS10"
    assert out["value"].to_list() == [3.95, 3.91]


def test_fred_network_failure_returns_empty_frame():
    def _raise(*_args, **_kwargs):
        raise OSError("dns failure")

    with patch("src.advisory.data_infra.ingestion.urllib.request.urlopen", side_effect=_raise):
        out = FREDConnector().fetch_series(
            "DGS10", date(2024, 1, 1), date(2024, 1, 5)
        )
    assert out.is_empty()


def test_yfinance_connector_empty_ticker_list():
    out = YFinanceConnector().fetch_daily_ohlcv([], date(2024, 1, 1), date(2024, 2, 1))
    assert out.is_empty()


def test_yfinance_connector_handles_download_exception():
    yconn = YFinanceConnector()

    class _FakeYf:
        @staticmethod
        def download(*_args, **_kwargs):
            raise RuntimeError("yfinance unreachable")

    yconn._yf = _FakeYf
    out = yconn.fetch_daily_ohlcv(["SPY"], date(2024, 1, 1), date(2024, 2, 1))
    assert out.is_empty()
