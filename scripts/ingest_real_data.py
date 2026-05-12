#!/usr/bin/env python3
"""Ingest real market data into ``features_pit``.

Free data sources, no API keys:

* **Yahoo Finance** (via :mod:`yfinance`) — daily OHLCV for equities + VIX.
* **FRED** — Treasury rates (DGS10, DGS2) and the HY OAS series
  (``BAMLH0A0HYM2``) via the public CSV endpoint.

Default universe = the architecture's macro factor proxies (SPY, TLT,
HYG, QQQ, IWD, IWM, UUP, DBC, SVXY, SMH) plus a few mega-caps so the
system has interpretable single-name examples.

Run:

    python scripts/ingest_real_data.py                    # default universe, last 10 years
    python scripts/ingest_real_data.py --tickers SPY AAPL MSFT
    python scripts/ingest_real_data.py --start 2020-01-01 --end 2024-12-31

Re-running is idempotent: rows with ``source = 'yfinance'`` /
``source = 'fred'`` are deleted before write.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

import polars as pl
import structlog

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from config.settings import settings  # noqa: E402
from src.advisory.data_infra.feature_store import FeatureStore  # noqa: E402
from src.advisory.data_infra.features import (  # noqa: E402
    compute_ohlcv_features,
    hy_spread_roc,
    vix_percentile_from_close,
    yield_curve_slope,
)
from src.advisory.data_infra.ingestion import (  # noqa: E402
    FREDConnector,
    YFinanceConnector,
)
from src.advisory.layer4_risk.factors import FACTOR_ORDER, MACRO_FACTOR_PROXIES  # noqa: E402
from src.advisory.layer0_validation.survivorship import SurvivorshipAuditor  # noqa: E402

logger = structlog.get_logger(__name__)


# Default ticker list = the architecture's macro proxies + a few mega-caps
DEFAULT_TICKERS: list[str] = [MACRO_FACTOR_PROXIES[k] for k in FACTOR_ORDER] + [
    "AAPL",
    "MSFT",
    "NVDA",
    "GOOGL",
    "AMZN",
]


FRED_SERIES: dict[str, str] = {
    "DGS10": "10-year Treasury yield",
    "DGS2": "2-year Treasury yield",
    "BAMLH0A0HYM2": "ICE BofA HY OAS",
}


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Ingest real market data into features_pit")
    p.add_argument(
        "--tickers",
        nargs="+",
        default=DEFAULT_TICKERS,
        help="Ticker symbols to fetch (default: macro factor proxies + mega-caps)",
    )
    p.add_argument(
        "--start",
        type=lambda s: date.fromisoformat(s),
        default=date.today() - timedelta(days=365 * 10),
        help="Start date (YYYY-MM-DD). Default: 10 years ago",
    )
    p.add_argument(
        "--end",
        type=lambda s: date.fromisoformat(s),
        default=date.today(),
        help="End date (YYYY-MM-DD). Default: today",
    )
    p.add_argument(
        "--skip-fred",
        action="store_true",
        help="Skip FRED macro fetch (Treasury rates + HY OAS)",
    )
    p.add_argument(
        "--keep-synthetic-delisted",
        action="store_true",
        help=(
            "Do NOT wipe synthetic delisted_tickers entries.  Default is "
            "to wipe them because they reference fake DEL### tickers that "
            "are not in any real universe.  Use this flag if you have "
            "loaded a real delisted-ticker source separately."
        ),
    )
    p.add_argument(
        "--keep-synthetic-features",
        action="store_true",
        help=(
            "Do NOT wipe synthetic feature rows.  Default is to delete "
            "rows with source='synthetic' so the validation pipeline "
            "averages over real data only.  Use this if you want to keep "
            "synthetic data side-by-side for comparison."
        ),
    )
    return p.parse_args()


def _wipe_existing(store: FeatureStore, source: str) -> None:
    store.conn.execute(
        "DELETE FROM features_pit WHERE source = ?", (source,)
    )


def main() -> None:
    args = _parse_args()
    print(
        f"Ingesting {len(args.tickers)} ticker(s) from {args.start} to {args.end}"
    )

    store = FeatureStore(settings.main_db_path, settings.cache_dir)
    try:
        # Wipe synthetic delisted entries (DEL###) unless the operator
        # has loaded a real delisted source.  Without this, the
        # survivorship audit expects to find fake tickers in the real
        # universe and reports FAIL.
        if not args.keep_synthetic_delisted:
            store.conn.execute(
                "DELETE FROM delisted_tickers WHERE ticker LIKE 'DEL%'"
            )
            print(
                "Wiped synthetic delisted tickers (DEL###).  Free data sources "
                "do not provide a clean delisted-tickers feed; survivorship "
                "coverage cannot be audited without one.  See README for "
                "options to populate the table manually."
            )

        # Wipe synthetic feature rows (source='synthetic') unless asked to
        # keep them.  Real-data validation should not average across fake
        # SYN### tickers.
        if not args.keep_synthetic_features:
            n_synth = store.conn.execute(
                "SELECT COUNT(*) FROM features_pit WHERE source = 'synthetic'"
            ).fetchone()
            n_synth_count = int(n_synth[0]) if n_synth else 0
            if n_synth_count:
                store.conn.execute(
                    "DELETE FROM features_pit WHERE source = 'synthetic'"
                )
                print(
                    f"Wiped {n_synth_count:,} synthetic feature rows so the "
                    "validation pipeline averages over real data only.  Use "
                    "--keep-synthetic-features to retain them side-by-side."
                )
        # ------------------------------------------------------------------
        # 1. Equity OHLCV via Yahoo Finance
        # ------------------------------------------------------------------
        yconn = YFinanceConnector()
        ohlcv = yconn.fetch_daily_ohlcv(args.tickers, args.start, args.end)
        if ohlcv.is_empty():
            print("WARNING: no equity OHLCV returned. Aborting.")
            return

        equity_features = compute_ohlcv_features(ohlcv)
        _wipe_existing(store, "yfinance")
        n_equity = store.write_features(
            equity_features, source="yfinance", version="v1"
        )

        # ------------------------------------------------------------------
        # 2. VIX (volatility regime feature)
        # ------------------------------------------------------------------
        vix_raw = yconn.fetch_daily_ohlcv(["^VIX"], args.start, args.end)
        n_vix = 0
        if not vix_raw.is_empty():
            vix_pct = vix_percentile_from_close(vix_raw.filter(pl.col("ticker") == "^VIX"))
            n_vix = store.write_features(
                vix_pct, source="yfinance", version="v1"
            )

        # ------------------------------------------------------------------
        # 3. Macro series via FRED
        # ------------------------------------------------------------------
        n_macro = 0
        if not args.skip_fred:
            fred = FREDConnector()
            series: dict[str, pl.DataFrame] = {}
            for sid in FRED_SERIES:
                series[sid] = fred.fetch_series(sid, args.start, args.end)
            macro_features: list[pl.DataFrame] = []
            if not series["DGS10"].is_empty() and not series["DGS2"].is_empty():
                macro_features.append(
                    yield_curve_slope(series["DGS10"], series["DGS2"])
                )
            if not series["BAMLH0A0HYM2"].is_empty():
                macro_features.append(hy_spread_roc(series["BAMLH0A0HYM2"]))
            if macro_features:
                combined_macro = pl.concat(macro_features).drop_nulls(
                    subset=["feature_value"]
                )
                _wipe_existing(store, "fred")
                n_macro = store.write_features(
                    combined_macro, source="fred", version="v1"
                )

        # ------------------------------------------------------------------
        # 4. Survivorship: with no delisted ticker history we record a
        #    note rather than fake a coverage number.
        # ------------------------------------------------------------------
        delisted_rows = store.conn.execute(
            "SELECT COUNT(*) FROM delisted_tickers"
        ).fetchone()
        delisted_count = int(delisted_rows[0]) if delisted_rows else 0

        if delisted_count >= 1:
            live = pl.DataFrame({"ticker": list(args.tickers)})
            delisted_df = pl.from_pandas(
                store.conn.execute(
                    "SELECT ticker, termination_date FROM delisted_tickers"
                ).fetch_df()
            )
            auditor = SurvivorshipAuditor(coverage_floor=0.95)
            survivorship = auditor.audit(
                live, delisted_df, args.start, args.end
            )
        else:
            survivorship = {
                "passed": False,
                "coverage": 0.0,
                "note": (
                    "No delisted ticker history present in DuckDB; "
                    "real-data ingest does not produce one.  Layer 0 "
                    "sign-off should fall back to research_preview until "
                    "a delisted-ticker source is wired."
                ),
            }

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------
        print(f"[OK] Equity feature rows:  {n_equity:,}")
        print(f"     VIX feature rows:     {n_vix:,}")
        print(f"     Macro feature rows:   {n_macro:,}")
        print(
            f"     Survivorship audit:   "
            f"{'PASSED' if survivorship['passed'] else 'NOT-RUN'} "
            f"(coverage {survivorship['coverage']:.3f})"
        )
        print(f"     Note: {survivorship.get('note', '')}")
    finally:
        store.close()


if __name__ == "__main__":
    main()
