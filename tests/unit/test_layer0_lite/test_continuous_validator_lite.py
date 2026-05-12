"""V7_lite Phase 5: Data Integrity Gate + widened divergence threshold."""
from __future__ import annotations

from datetime import date

import numpy as np
import polars as pl

from src.advisory.layer0_validation.continuous_validator import ContinuousValidator


def _paper_log(n: int = 120) -> pl.DataFrame:
    rng = np.random.default_rng(0)
    return pl.DataFrame({"pnl_pct": rng.normal(0.0006, 0.01, size=n)})


def _audit(n_total: int, n_missing: int = 0, n_stale: int = 0) -> pl.DataFrame:
    statuses = ["OK"] * (n_total - n_missing) + ["MISSING"] * n_missing
    rows = []
    for i, s in enumerate(statuses):
        rows.append(
            {
                "ticker": f"T{i:03d}",
                "fetch_date": date(2024, 1, 1),
                "status": s,
                "n_rows": 0 if (s == "OK" and i < n_stale) else (
                    0 if s == "MISSING" else 1
                ),
                "n_bad_rows": 0,
                "n_consec_gaps": 0,
                "note": None,
                "app_mode": "v7_lite",
            }
        )
    return pl.DataFrame(rows)


def test_divergence_thresholds_pinned():
    cv = ContinuousValidator()
    assert cv.DIVERGENCE_THRESHOLD_INSTITUTIONAL == 0.30
    assert cv.DIVERGENCE_THRESHOLD_LITE == 0.40


def test_data_integrity_pauses_on_missing_bars():
    cv = ContinuousValidator()
    # 5% missing > 2% ceiling
    result = cv.reassess(
        layer_name="layer1",
        pre_deployment_sharpe=1.0,
        paper_trade_log=_paper_log(),
        adapter_audit=_audit(n_total=100, n_missing=5),
        app_mode="v7_lite",
    )
    assert result["status"] == "VALIDATION_PAUSED_DATA_INTEGRITY"
    assert result["demote_to_research"] is False


def test_data_integrity_pauses_on_stale_cross_ticker():
    cv = ContinuousValidator()
    # 100 OK but 30 of them have 0 rows → stale_frac = 0.30 > 0.20
    result = cv.reassess(
        layer_name="layer1",
        pre_deployment_sharpe=1.0,
        paper_trade_log=_paper_log(),
        adapter_audit=_audit(n_total=100, n_missing=0, n_stale=30),
        app_mode="v7_lite",
    )
    assert result["status"] == "VALIDATION_PAUSED_DATA_INTEGRITY"


def test_data_integrity_ok_runs_divergence_check():
    cv = ContinuousValidator()
    result = cv.reassess(
        layer_name="layer1",
        pre_deployment_sharpe=1.0,
        paper_trade_log=_paper_log(),
        adapter_audit=_audit(n_total=100, n_missing=0, n_stale=0),
        app_mode="v7_lite",
    )
    assert result["status"] in ("OK", "INSUFFICIENT_PAPER_DATA")


def test_institutional_path_unchanged():
    cv = ContinuousValidator()
    # No adapter_audit; institutional mode → original divergence threshold (0.30)
    result = cv.reassess(
        layer_name="layer1",
        pre_deployment_sharpe=1.0,
        paper_trade_log=_paper_log(),
        adapter_audit=None,
        app_mode="v7_institutional",
    )
    # The threshold seen inside the check should be 0.30
    assert result["divergence_threshold"] == 0.30


def test_lite_uses_wider_threshold():
    cv = ContinuousValidator()
    result = cv.reassess(
        layer_name="layer1",
        pre_deployment_sharpe=1.0,
        paper_trade_log=_paper_log(),
        adapter_audit=None,
        app_mode="v7_lite",
    )
    assert result["divergence_threshold"] == 0.40
