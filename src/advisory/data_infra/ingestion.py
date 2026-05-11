"""Thin source connectors.  Stub implementations: each method logs the
request and returns an empty DataFrame with the correct schema on
failure.  Real HTTP wiring lives behind injectable clients.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

import polars as pl
import structlog

logger = structlog.get_logger(__name__)


class HttpClient(Protocol):
    """Injectable HTTP client interface — keeps connectors test-friendly."""

    def get(self, url: str, params: dict[str, Any] | None = None) -> Any:
        ...


@dataclass
class _StubClient:
    """No-op HTTP client used when an API key is absent."""

    def get(self, url: str, params: dict[str, Any] | None = None) -> Any:
        return None


_OHLCV_SCHEMA = {
    "ticker": pl.Utf8,
    "effective_date": pl.Date,
    "open": pl.Float64,
    "high": pl.Float64,
    "low": pl.Float64,
    "close": pl.Float64,
    "volume": pl.Float64,
}

_FEATURE_SCHEMA = {
    "ticker": pl.Utf8,
    "effective_date": pl.Date,
    "knowledge_date": pl.Date,
    "feature_name": pl.Utf8,
    "feature_value": pl.Float64,
}


class PolygonConnector:
    """Daily OHLCV + 1-min bars + options chain (stub)."""

    def __init__(self, api_key: str = "", client: HttpClient | None = None):
        self.api_key = api_key
        self.client = client or _StubClient()

    def fetch_daily_ohlcv(
        self, tickers: list[str], start: date, end: date
    ) -> pl.DataFrame:
        logger.info(
            "polygon_fetch_daily_ohlcv",
            n_tickers=len(tickers),
            start=str(start),
            end=str(end),
            stub=isinstance(self.client, _StubClient),
        )
        return pl.DataFrame(schema=_OHLCV_SCHEMA)

    def fetch_intraday_bars(
        self, ticker: str, on_date: date, multiplier: int = 1
    ) -> pl.DataFrame:
        logger.info(
            "polygon_fetch_intraday_bars",
            ticker=ticker,
            on_date=str(on_date),
            multiplier=multiplier,
        )
        return pl.DataFrame(
            schema={
                "ticker": pl.Utf8,
                "minute": pl.Datetime,
                "bid": pl.Float64,
                "ask": pl.Float64,
                "volume": pl.Float64,
            }
        )


class SharadarConnector:
    """Point-in-time fundamentals (stub)."""

    def __init__(self, api_key: str = "", client: HttpClient | None = None):
        self.api_key = api_key
        self.client = client or _StubClient()

    def fetch_earnings_revisions(
        self, tickers: list[str], start: date, end: date
    ) -> pl.DataFrame:
        logger.info(
            "sharadar_fetch_earnings_revisions",
            n_tickers=len(tickers),
        )
        return pl.DataFrame(schema=_FEATURE_SCHEMA)

    def fetch_fundamentals(
        self, tickers: list[str], start: date, end: date
    ) -> pl.DataFrame:
        logger.info("sharadar_fetch_fundamentals", n_tickers=len(tickers))
        return pl.DataFrame(schema=_FEATURE_SCHEMA)


class FREDConnector:
    """Macro series (stub)."""

    def __init__(self, api_key: str = "", client: HttpClient | None = None):
        self.api_key = api_key
        self.client = client or _StubClient()

    def fetch_series(
        self, series_id: str, start: date, end: date
    ) -> pl.DataFrame:
        logger.info(
            "fred_fetch_series",
            series_id=series_id,
            start=str(start),
            end=str(end),
        )
        return pl.DataFrame(
            schema={
                "series_id": pl.Utf8,
                "effective_date": pl.Date,
                "value": pl.Float64,
            }
        )


class CBOEConnector:
    """Options-surface connector (stub)."""

    def __init__(self, client: HttpClient | None = None):
        self.client = client or _StubClient()

    def fetch_options_surface(self, on_date: date) -> pl.DataFrame:
        logger.info("cboe_fetch_options_surface", on_date=str(on_date))
        return pl.DataFrame(
            schema={
                "ticker": pl.Utf8,
                "effective_date": pl.Date,
                "iv_skew": pl.Float64,
                "put_call_ratio": pl.Float64,
            }
        )
