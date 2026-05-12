"""V7_lite feature pipeline.

Builds the 9-dimensional feature vector consumed by ``hmm_v7_lite.pkl``.
Each dimension may be backed by multiple raw features — they are
averaged within the dimension before HMM input, so the HMM always sees
9 scalar values per observation.

This module **supplements** the V7 Institutional feature pipeline; it
does not replace anything.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl
import structlog

logger = structlog.get_logger(__name__)


# The architecture-pinned set of 11 sector ETFs.
SECTOR_ETFS: tuple[str, ...] = (
    "XLK", "XLF", "XLV", "XLY", "XLP", "XLE",
    "XLI", "XLB", "XLRE", "XLU", "XLC",
)

# Ordered dimension names — the HMM and the dashboard both rely on this order.
DIMENSION_ORDER: tuple[str, ...] = (
    "trend",
    "volatility",
    "breadth",
    "liquidity",
    "macro",
    "correlation",
    "options_proxy",
    "sector_relative_return",
    "fundamental",
)


class ConfigurationError(RuntimeError):
    """Raised when the lite feature pipeline is mis-configured."""


def load_sector_map(path: Path | str | None = None) -> dict[str, str]:
    """Load ``config/sector_map.yaml`` as a ``{ticker: etf}`` dict.

    YAML is parsed without a third-party dependency to keep the
    runtime surface small — the file format is simple key/value with
    optional comments.
    """
    p = Path(path) if path else Path("config/sector_map.yaml")
    if not p.exists():
        raise ConfigurationError(f"sector map not found: {p}")
    out: dict[str, str] = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            continue
        ticker, etf = stripped.split(":", 1)
        out[ticker.strip()] = etf.strip()
    return out


def validate_sector_map(
    tickers: list[str], sector_map: dict[str, str]
) -> dict[str, Any]:
    """Verify (a) every analytical-universe ticker has a mapping and
    (b) every mapped ETF is in :data:`SECTOR_ETFS`.

    Raises :class:`ConfigurationError` on either failure.
    """
    missing_tickers = [t for t in tickers if t not in sector_map]
    if missing_tickers:
        raise ConfigurationError(
            f"sector map missing {len(missing_tickers)} tickers: "
            f"{missing_tickers[:10]}{'...' if len(missing_tickers) > 10 else ''}"
        )
    unknown_etfs = sorted(
        {etf for etf in sector_map.values() if etf not in SECTOR_ETFS}
    )
    if unknown_etfs:
        raise ConfigurationError(
            f"sector map references {len(unknown_etfs)} ETF(s) outside "
            f"SECTOR_ETFS: {unknown_etfs}"
        )
    return {
        "passed": True,
        "n_tickers": len(tickers),
        "n_etfs": len(set(sector_map.values())),
    }


# ---------------------------------------------------------------------- #
# Raw feature builders
# ---------------------------------------------------------------------- #


def sector_relative_return_252d(
    asset_close: pl.Series,
    etf_close: pl.Series,
) -> float:
    """``(asset_t / asset_{t-252}) - (etf_t / etf_{t-252})``.

    Returns ``float('nan')`` when either series has < 252 bars — that
    NaN is fed into the HMM input via :func:`build_lite_feature_vector`
    after the standard winsorisation/normalisation step, which forward-
    fills short gaps and clips to zero on long gaps.
    """
    a = asset_close.to_numpy()
    e = etf_close.to_numpy()
    if a.size < 252 or e.size < 252:
        return float("nan")
    asset_ret = a[-1] / a[-252] - 1.0
    etf_ret = e[-1] / e[-252] - 1.0
    return float(asset_ret - etf_ret)


def ma_spread_50_200d(close: pl.Series) -> float:
    arr = close.to_numpy()
    if arr.size < 200:
        return float("nan")
    ma50 = float(np.mean(arr[-50:]))
    ma200 = float(np.mean(arr[-200:]))
    if ma200 == 0:
        return float("nan")
    return (ma50 - ma200) / ma200


def atr_pct_21d(
    high: pl.Series, low: pl.Series, close: pl.Series, window: int = 21
) -> float:
    h = high.to_numpy()
    l = low.to_numpy()
    c = close.to_numpy()
    if c.size < window + 1:
        return float("nan")
    tr = np.maximum.reduce(
        [
            h[1:] - l[1:],
            np.abs(h[1:] - c[:-1]),
            np.abs(l[1:] - c[:-1]),
        ]
    )
    atr = float(np.mean(tr[-window:]))
    last_close = float(c[-1])
    return atr / last_close if last_close else float("nan")


def vix_term_slope(vix_3m: float, vix_1m: float) -> float:
    """``vix_3m - vix_1m``.  Positive = contango (calm), negative = stress."""
    if np.isnan(vix_3m) or np.isnan(vix_1m):
        return float("nan")
    return float(vix_3m - vix_1m)


# ---------------------------------------------------------------------- #
# 9-dim feature vector builder
# ---------------------------------------------------------------------- #


def _safe_mean(values: list[float]) -> float:
    """Mean of finite values; NaN when none are finite."""
    finite = [v for v in values if v is not None and np.isfinite(v)]
    if not finite:
        return float("nan")
    return float(np.mean(finite))


def build_lite_feature_vector(
    ticker: str,
    ohlcv_history: pl.DataFrame,
    sector_etf_history: pl.DataFrame,
    macro_history: pl.DataFrame,
    options_proxy: pl.DataFrame,
    sector_map: dict[str, str],
    as_of_date: date,
) -> np.ndarray:
    """Assemble the 9-dimensional feature vector for the lite HMM.

    All sub-features within a dimension are averaged into one scalar
    before being placed in the output array.

    Parameters
    ----------
    ohlcv_history:
        Daily bars for ``ticker`` up to ``as_of_date``.
    sector_etf_history:
        Daily bars for the sector ETF mapped to ``ticker``.
    macro_history:
        FRED rows: columns include ``hy_oas``, ``ig_oas``, ``yield_curve_slope``,
        ``treasury_10yr_roc_21d``.
    options_proxy:
        Daily rows of options-proxy sub-features (``vix_9d``, ``vix_1m``,
        ``vix_3m``, ``skew_index``, ``put_call_ratio``).
    sector_map:
        ``{ticker: sector_etf}``.
    """
    out = np.full(len(DIMENSION_ORDER), float("nan"), dtype=float)

    if "close" in ohlcv_history.columns and ohlcv_history.height:
        close = ohlcv_history.sort("effective_date")["close"]
        ret_1d = close.pct_change().tail(1).to_list()
        ret_5d = (close.tail(1) / close.tail(6).head(1) - 1.0).to_list()
        ret_21d = (close.tail(1) / close.tail(22).head(1) - 1.0).to_list()
        ma_spread = ma_spread_50_200d(close)
        out[DIMENSION_ORDER.index("trend")] = _safe_mean(
            [v for v in (ret_1d + ret_5d + ret_21d + [ma_spread]) if v is not None]
        )

        vol = close.pct_change().tail(21).std()
        atr = atr_pct_21d(ohlcv_history["high"], ohlcv_history["low"], close)
        out[DIMENSION_ORDER.index("volatility")] = _safe_mean(
            [vol if vol is not None else float("nan"), atr]
        )

        if "volume" in ohlcv_history.columns:
            vol_arr = ohlcv_history["volume"].to_numpy().astype(float)
            if vol_arr.size >= 21:
                norm = vol_arr[-1] / max(np.mean(vol_arr[-21:]), 1e-12)
                out[DIMENSION_ORDER.index("liquidity")] = float(norm)

    # Macro dimension — averages whichever FRED sub-features are present.
    macro_values: list[float] = []
    for col in ("hy_oas", "ig_oas", "yield_curve_slope", "treasury_10yr_roc_21d"):
        if col in macro_history.columns and macro_history.height:
            macro_values.append(float(macro_history[col].tail(1)[0] or float("nan")))
    out[DIMENSION_ORDER.index("macro")] = _safe_mean(macro_values)

    # Options proxy dimension — averages all sub-features (incl. derived
    # vix_term_slope when both 1m and 3m are present).
    opt_values: list[float] = []
    for col in ("vix_9d", "vix_1m", "vix_3m", "skew_index", "put_call_ratio"):
        if col in options_proxy.columns and options_proxy.height:
            opt_values.append(float(options_proxy[col].tail(1)[0] or float("nan")))
    if (
        "vix_3m" in options_proxy.columns
        and "vix_1m" in options_proxy.columns
        and options_proxy.height
    ):
        opt_values.append(
            vix_term_slope(
                float(options_proxy["vix_3m"].tail(1)[0] or float("nan")),
                float(options_proxy["vix_1m"].tail(1)[0] or float("nan")),
            )
        )
    out[DIMENSION_ORDER.index("options_proxy")] = _safe_mean(opt_values)

    # Sector-relative-return dimension
    if sector_etf_history.height and "close" in sector_etf_history.columns:
        srr = sector_relative_return_252d(
            ohlcv_history["close"], sector_etf_history["close"]
        )
        out[DIMENSION_ORDER.index("sector_relative_return")] = srr

    # Breadth and correlation dimensions need cross-sectional inputs not
    # available from a single ticker — they are filled by the orchestrator
    # at the universe level.  Leave NaN here.
    return out
