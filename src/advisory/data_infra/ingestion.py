"""Source connectors.

Two flavours co-exist:

* **Stub** connectors (PolygonConnector, SharadarConnector, CBOEConnector
  by default) return empty frames so the rest of the pipeline can be
  exercised without API keys.
* **Real** connectors (:class:`YFinanceConnector`, :class:`FREDConnector`)
  fetch real market data from free endpoints.  No API key is required for
  either — yfinance scrapes Yahoo Finance, FRED publishes a free CSV
  endpoint at ``https://fred.stlouisfed.org/graph/fredgraph.csv``.

The split keeps the architecture honest: the stub connectors document
that a paid data source would be plugged in here, while the real
connectors give the operator a working ingest path on day one.
"""
from __future__ import annotations

import io
import urllib.request
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

import pandas as pd
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
    """FRED macro series via the public CSV endpoint (no API key required).

    Uses ``https://fred.stlouisfed.org/graph/fredgraph.csv?id=<SERIES>``,
    which is the same endpoint the FRED website uses for chart downloads.
    Returns an empty DataFrame on any failure so the rest of the pipeline
    can continue.
    """

    _CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
    _TIMEOUT_SECONDS = 30

    def __init__(self, api_key: str = "", client: HttpClient | None = None):
        # api_key kept for forward-compatibility; CSV endpoint doesn't need one.
        self.api_key = api_key
        self.client = client

    def fetch_series(
        self, series_id: str, start: date, end: date
    ) -> pl.DataFrame:
        logger.info(
            "fred_fetch_series",
            series_id=series_id,
            start=str(start),
            end=str(end),
        )
        url = (
            f"{self._CSV_URL}?id={series_id}"
            f"&cosd={start.isoformat()}&coed={end.isoformat()}"
        )
        try:
            with urllib.request.urlopen(url, timeout=self._TIMEOUT_SECONDS) as resp:
                payload = resp.read()
        except Exception as exc:  # pragma: no cover - network path
            logger.warning("fred_fetch_failed", series_id=series_id, error=str(exc))
            return pl.DataFrame(
                schema={
                    "series_id": pl.Utf8,
                    "effective_date": pl.Date,
                    "value": pl.Float64,
                }
            )

        df = pd.read_csv(io.BytesIO(payload))
        # FRED uses "." for missing values
        df = df.rename(columns={df.columns[0]: "effective_date"})
        value_col = df.columns[1]
        df["value"] = pd.to_numeric(df[value_col], errors="coerce")
        df = df.dropna(subset=["value"])
        if df.empty:
            return pl.DataFrame(
                schema={
                    "series_id": pl.Utf8,
                    "effective_date": pl.Date,
                    "value": pl.Float64,
                }
            )
        df["effective_date"] = pd.to_datetime(df["effective_date"]).dt.date
        df["series_id"] = series_id
        return pl.from_pandas(df[["series_id", "effective_date", "value"]])


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


class YFinanceConnector:
    """Daily OHLCV via Yahoo Finance — free, no API key.

    Suitable for prototyping and the operator's first real-data ingest.
    In production it would be replaced by Polygon / Sharadar / similar
    paid sources (the stub :class:`PolygonConnector` documents that
    contract).
    """

    def __init__(self) -> None:
        # yfinance is imported lazily so the module loads without it.
        self._yf = None

    def _import_yf(self):
        if self._yf is None:
            import yfinance as yf  # local import: optional dep at runtime

            self._yf = yf
        return self._yf

    def fetch_daily_ohlcv(
        self, tickers: list[str], start: date, end: date
    ) -> pl.DataFrame:
        """Return one row per (ticker, date) with adjusted OHLCV."""
        logger.info(
            "yfinance_fetch_daily_ohlcv",
            n_tickers=len(tickers),
            start=str(start),
            end=str(end),
        )
        if not tickers:
            return pl.DataFrame(schema=_OHLCV_SCHEMA)

        yf = self._import_yf()
        try:
            raw = yf.download(
                tickers=tickers,
                start=start.isoformat(),
                # yfinance treats `end` as exclusive; add 1 day on the caller side.
                end=end.isoformat(),
                auto_adjust=True,
                progress=False,
                group_by="ticker",
                threads=True,
            )
        except Exception as exc:  # pragma: no cover - network path
            logger.warning("yfinance_fetch_failed", error=str(exc))
            return pl.DataFrame(schema=_OHLCV_SCHEMA)

        if raw is None or raw.empty:
            return pl.DataFrame(schema=_OHLCV_SCHEMA)

        frames: list[pd.DataFrame] = []
        # Single ticker -> flat columns; multi-ticker -> MultiIndex columns.
        if isinstance(raw.columns, pd.MultiIndex):
            for ticker in raw.columns.get_level_values(0).unique():
                sub = raw[ticker].copy()
                sub = sub.dropna(how="all").reset_index()
                sub["ticker"] = ticker
                frames.append(sub)
        else:
            sub = raw.copy().dropna(how="all").reset_index()
            sub["ticker"] = tickers[0]
            frames.append(sub)

        merged = pd.concat(frames, ignore_index=True)
        merged.columns = [str(c).lower() for c in merged.columns]
        merged = merged.rename(columns={"date": "effective_date"})
        merged["effective_date"] = pd.to_datetime(merged["effective_date"]).dt.date
        wanted = ["ticker", "effective_date", "open", "high", "low", "close", "volume"]
        missing = [c for c in wanted if c not in merged.columns]
        if missing:
            logger.warning("yfinance_missing_columns", missing=missing)
            return pl.DataFrame(schema=_OHLCV_SCHEMA)
        merged = merged[wanted].dropna(subset=["close"])
        for col in ("open", "high", "low", "close", "volume"):
            merged[col] = merged[col].astype(float)
        return pl.from_pandas(merged)
