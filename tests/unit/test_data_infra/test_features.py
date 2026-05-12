"""Tests for the OHLCV → feature computation module."""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import polars as pl
import pytest

from src.advisory.data_infra.features import (
    FORWARD_WINDOW,
    MA_WINDOW,
    VOL_WINDOW,
    compute_ohlcv_features,
    hy_spread_roc,
    vix_percentile_from_close,
    yield_curve_slope,
)


def _ohlcv(ticker: str, n: int = 100, seed: int = 0) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    base = 100.0
    log_steps = rng.normal(0.0005, 0.012, size=n)
    closes = base * np.cumprod(np.exp(log_steps))
    start = date(2024, 1, 1)
    dates = [start + timedelta(days=i) for i in range(n)]
    return pl.DataFrame(
        {
            "ticker": [ticker] * n,
            "effective_date": dates,
            "open": closes,
            "high": closes * 1.005,
            "low": closes * 0.995,
            "close": closes,
            "volume": np.full(n, 1e6),
        }
    )


def test_compute_features_returns_long_format():
    df = compute_ohlcv_features(_ohlcv("AAPL"))
    assert {
        "ticker",
        "effective_date",
        "knowledge_date",
        "feature_name",
        "feature_value",
    }.issubset(set(df.columns))
    assert df.height > 0


def test_compute_features_emits_expected_feature_names():
    df = compute_ohlcv_features(_ohlcv("AAPL"))
    names = set(df["feature_name"].unique().to_list())
    expected = {
        "ret_1d",
        "ret_5d",
        "ret_21d",
        "ret_63d",
        f"realized_vol_{VOL_WINDOW}d",
        "rsi_14",
        "pct_above_ma50",
        f"ret_fwd_{FORWARD_WINDOW}d",
    }
    assert expected.issubset(names)


def test_compute_features_handles_multiple_tickers():
    ohlcv = pl.concat([_ohlcv("AAPL", seed=1), _ohlcv("MSFT", seed=2)])
    df = compute_ohlcv_features(ohlcv)
    tickers = set(df["ticker"].unique().to_list())
    assert tickers == {"AAPL", "MSFT"}


def test_compute_features_rejects_missing_required_columns():
    df = pl.DataFrame({"ticker": ["X"], "effective_date": [date(2024, 1, 1)]})
    with pytest.raises(ValueError):
        compute_ohlcv_features(df)


def test_rsi_in_unit_range():
    df = compute_ohlcv_features(_ohlcv("AAPL", n=200))
    rsi = df.filter(pl.col("feature_name") == "rsi_14")["feature_value"].to_numpy()
    assert (rsi >= 0).all() and (rsi <= 100).all()


def test_ma_window_warm_up_period_dropped():
    df = compute_ohlcv_features(_ohlcv("AAPL", n=80))
    ma = df.filter(pl.col("feature_name") == "pct_above_ma50")
    # First MA_WINDOW-1 entries are NaN-dropped
    assert ma.height <= 80 - MA_WINDOW + 1


def test_vix_percentile_uses_rolling_window():
    closes = list(range(1, 100))
    vix = pl.DataFrame(
        {"effective_date": [date(2024, 1, 1) + timedelta(days=i) for i in range(len(closes))],
         "close": [float(c) for c in closes]}
    )
    out = vix_percentile_from_close(vix, window=10)
    values = out["feature_value"].drop_nulls().to_numpy()
    # Monotone-increasing series has rising percentiles
    assert values[-1] >= values[0]
    # All values in [0, 1]
    assert (values >= 0).all() and (values <= 1).all()


def test_yield_curve_slope_subtraction():
    d = [date(2024, 1, i + 1) for i in range(5)]
    dgs10 = pl.DataFrame({"effective_date": d, "value": [4.0, 4.1, 4.2, 4.3, 4.4]})
    dgs2 = pl.DataFrame({"effective_date": d, "value": [3.0, 3.0, 3.1, 3.2, 3.3]})
    out = yield_curve_slope(dgs10, dgs2)
    vals = out["feature_value"].drop_nulls().to_list()
    assert vals == pytest.approx([1.0, 1.1, 1.1, 1.1, 1.1])


def test_hy_spread_roc_rate_of_change():
    d = [date(2024, 1, 1) + timedelta(days=i) for i in range(40)]
    # Linear ramp: 1, 1.1, 1.2, ...
    vals = [1.0 + 0.1 * i for i in range(40)]
    hy = pl.DataFrame({"effective_date": d, "value": vals})
    out = hy_spread_roc(hy, window=21)
    series = out["feature_value"].drop_nulls().to_numpy()
    assert series.size > 0
    # Rate of change is positive throughout (HY widening trend)
    assert (series > 0).all()


def test_yield_curve_slope_empty_input():
    out = yield_curve_slope(pl.DataFrame(), pl.DataFrame())
    assert out.is_empty()
