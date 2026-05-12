"""V7_lite Phase 3: sector map + lite feature pipeline."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl
import pytest

from src.advisory.data_infra.feature_pipeline_lite import (
    ConfigurationError,
    DIMENSION_ORDER,
    SECTOR_ETFS,
    load_sector_map,
    sector_relative_return_252d,
    validate_sector_map,
    vix_term_slope,
)


def test_sector_map_loads():
    m = load_sector_map()
    assert m["AAPL"] == "XLK"
    assert m["XOM"] == "XLE"


def test_validate_sector_map_raises_on_missing_ticker():
    m = load_sector_map()
    with pytest.raises(ConfigurationError):
        validate_sector_map(["AAPL", "MISSING_TICKER_XYZ"], m)


def test_validate_sector_map_raises_on_unknown_etf():
    m = {"AAPL": "ZZZ_NOT_AN_ETF"}
    with pytest.raises(ConfigurationError):
        validate_sector_map(["AAPL"], m)


def test_sector_relative_return_nan_when_insufficient_bars():
    short = pl.Series([100.0, 101.0, 102.0])
    out = sector_relative_return_252d(short, short)
    assert np.isnan(out)


def test_sector_relative_return_correct_formula():
    asset = pl.Series([100.0 * (1 + i * 0.001) for i in range(300)])
    etf = pl.Series([100.0 * (1 + i * 0.0005) for i in range(300)])
    out = sector_relative_return_252d(asset, etf)
    # Asset rose more than ETF over the 252-day window → positive slope.
    assert out > 0


def test_dimension_order_has_9_entries():
    assert len(DIMENSION_ORDER) == 9


def test_sector_etfs_set_pinned():
    assert "XLK" in SECTOR_ETFS
    assert len(SECTOR_ETFS) == 11


def test_vix_term_slope_contango_positive():
    assert vix_term_slope(20.0, 18.0) == 2.0


def test_vix_term_slope_backwardation_negative():
    assert vix_term_slope(15.0, 20.0) == -5.0


def test_vix_term_slope_nan_input_propagates():
    assert np.isnan(vix_term_slope(np.nan, 20.0))
