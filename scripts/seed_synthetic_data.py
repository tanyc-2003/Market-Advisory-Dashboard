#!/usr/bin/env python3
"""Populate the main DB with synthetic features for 100 tickers over 10 years.

Deterministic (seed=42).  Used by tests and local development.  Includes
20 synthetic delisted tickers spread across the history window so
:class:`SurvivorshipAuditor` will pass at ``coverage_floor=0.95``.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import polars as pl

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from config.settings import settings  # noqa: E402
from src.advisory.data_infra.feature_store import FeatureStore  # noqa: E402
from src.advisory.layer0_validation.survivorship import SurvivorshipAuditor  # noqa: E402

SEED = 42

UNIVERSE_SIZE = 100
N_DELISTED = 20
HISTORY_YEARS = 10
N_TRADING_DAYS = HISTORY_YEARS * 252

FEATURES = [
    "ret_1d",
    "ret_5d",
    "ret_21d",
    "realized_vol_21d",
    "vix_percentile_63d",
    "hy_spread_roc_21d",
    "yield_curve_slope",
    "earnings_revision_z",
    "pct_above_ma50",
    "iv_rv_ratio",
    "ret_fwd_10d",
]


def _business_days(end: date, n: int) -> list[date]:
    out: list[date] = []
    cursor = end
    while len(out) < n:
        if cursor.weekday() < 5:
            out.append(cursor)
        cursor -= timedelta(days=1)
    return list(reversed(out))


def main() -> None:
    rng = np.random.default_rng(SEED)
    end = date(2024, 12, 31)
    business_days = _business_days(end, N_TRADING_DAYS)

    live_tickers = [f"SYN{ix:03d}" for ix in range(UNIVERSE_SIZE)]
    delisted_tickers = [f"DEL{ix:03d}" for ix in range(N_DELISTED)]

    delisted_rows = []
    for t in delisted_tickers:
        idx = int(rng.integers(252, N_TRADING_DAYS - 252))
        delisted_rows.append(
            {
                "ticker": t,
                "termination_date": business_days[idx],
                "termination_reason": rng.choice(
                    ["merger", "bankruptcy", "acquisition", "voluntary", "unknown"]
                ),
                "terminal_return": float(rng.normal(-0.1, 0.3)),
            }
        )
    delisted_df = pl.DataFrame(delisted_rows)

    settings.main_db_path.parent.mkdir(parents=True, exist_ok=True)
    settings.cache_dir.mkdir(parents=True, exist_ok=True)

    store = FeatureStore(settings.main_db_path, settings.cache_dir)
    try:
        # Wipe-and-replace synthetic seed (idempotent re-runs).
        store.conn.execute("DELETE FROM features_pit WHERE source = 'synthetic'")
        store.conn.execute("DELETE FROM delisted_tickers")
        if delisted_rows:
            store.conn.register("__delisted__", delisted_df.to_arrow())
            store.conn.execute(
                "INSERT INTO delisted_tickers SELECT * FROM __delisted__"
            )
            store.conn.unregister("__delisted__")

        # Generate features per ticker, per day.
        all_tickers = live_tickers + delisted_tickers
        total_rows = 0
        for t in all_tickers:
            term: date | None = None
            if t.startswith("DEL"):
                term = next(
                    r["termination_date"]
                    for r in delisted_rows
                    if r["ticker"] == t
                )
            n_days = N_TRADING_DAYS if term is None else (
                next(i for i, d in enumerate(business_days) if d >= term) + 1
            )
            days = business_days[:n_days]
            base_drift = float(rng.normal(0.0005, 0.0005))
            base_vol = float(rng.uniform(0.008, 0.025))
            shocks = rng.normal(base_drift, base_vol, size=n_days)
            ret_1d = shocks
            cum = np.cumprod(1 + shocks)

            feature_values: dict[str, np.ndarray] = {
                "ret_1d": ret_1d,
                "ret_5d": np.concatenate(
                    [np.zeros(5), cum[5:] / cum[:-5] - 1.0]
                ),
                "ret_21d": np.concatenate(
                    [np.zeros(21), cum[21:] / cum[:-21] - 1.0]
                ),
                "realized_vol_21d": pl.Series(ret_1d)
                .rolling_std(window_size=21, min_periods=21)
                .fill_null(base_vol)
                .to_numpy()
                * np.sqrt(252),
                "vix_percentile_63d": rng.uniform(0.0, 1.0, size=n_days),
                "hy_spread_roc_21d": rng.normal(0.0, 0.05, size=n_days),
                "yield_curve_slope": rng.normal(0.5, 0.4, size=n_days),
                "earnings_revision_z": rng.normal(0.0, 1.0, size=n_days),
                "pct_above_ma50": rng.uniform(0.0, 1.0, size=n_days),
                "iv_rv_ratio": rng.uniform(0.8, 1.4, size=n_days),
                "ret_fwd_10d": np.concatenate(
                    [
                        cum[10:] / cum[:-10] - 1.0,
                        np.zeros(10),
                    ]
                ),
            }

            rows_per_feature: list[dict] = []
            for feature_name, values in feature_values.items():
                for d, v in zip(days, values):
                    rows_per_feature.append(
                        {
                            "ticker": t,
                            "effective_date": d,
                            "knowledge_date": d,
                            "feature_name": feature_name,
                            "feature_value": float(v),
                        }
                    )
            df = pl.DataFrame(rows_per_feature)
            total_rows += store.write_features(df, source="synthetic", version="v1")

        # Verify survivorship coverage.
        auditor = SurvivorshipAuditor(coverage_floor=0.95)
        live_df = pl.DataFrame({"ticker": all_tickers})
        delisted_check = delisted_df.select(["ticker", "termination_date"])
        result = auditor.audit(
            live_df,
            delisted_check,
            window_start=business_days[0],
            window_end=business_days[-1],
        )

        print(f"[OK] Synthetic data seeded: {total_rows:,} feature rows")
        print(f"     Tickers: {len(all_tickers)} ({UNIVERSE_SIZE} live + {N_DELISTED} delisted)")
        print(f"     Date range: {business_days[0]} -> {business_days[-1]}")
        print(f"     Survivorship coverage: {result['coverage']:.3f} "
              f"(passed={result['passed']})")
    finally:
        store.close()


if __name__ == "__main__":
    main()
