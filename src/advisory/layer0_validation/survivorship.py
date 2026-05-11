"""Survivorship audit.

Verifies that the live universe used by upstream layers also includes a
plausible representation of *delisted* / terminated tickers.  A universe
that only contains survivors silently overstates every backtest, so this
audit gates the entire validation substrate.
"""
from __future__ import annotations

from datetime import date
from typing import Iterable

import polars as pl
import structlog

logger = structlog.get_logger(__name__)


class SurvivorshipAuditError(RuntimeError):
    """Raised when the survivorship audit fails.  Blocks downstream validation."""


class SurvivorshipAuditor:
    """Audit the live universe against a list of known delisted tickers.

    Parameters
    ----------
    coverage_floor:
        Minimum fraction of expected delisted tickers that must appear in
        the supplied live data window.  Default 0.95.  Cannot be set below
        0.80; this is an architectural floor.
    """

    MIN_COVERAGE_FLOOR: float = 0.80

    def __init__(self, coverage_floor: float = 0.95) -> None:
        if coverage_floor < self.MIN_COVERAGE_FLOOR:
            raise ValueError(
                f"coverage_floor={coverage_floor} is below the architectural "
                f"floor {self.MIN_COVERAGE_FLOOR}.  Bypassing this would mask "
                f"survivorship bias."
            )
        self.coverage_floor = coverage_floor

    def audit(
        self,
        live_universe: pl.DataFrame,
        delisted_universe: pl.DataFrame,
        window_start: date,
        window_end: date,
    ) -> dict:
        """Audit coverage of delisted tickers within the requested window.

        ``live_universe`` and ``delisted_universe`` must each carry a
        ``ticker`` column.  ``delisted_universe`` must also carry
        ``termination_date``.  Tickers whose ``termination_date`` falls
        within ``[window_start, window_end]`` are expected to be present
        in ``live_universe``.
        """
        if "ticker" not in live_universe.columns:
            raise ValueError("live_universe must contain a `ticker` column")
        if "ticker" not in delisted_universe.columns:
            raise ValueError("delisted_universe must contain a `ticker` column")
        if "termination_date" not in delisted_universe.columns:
            raise ValueError("delisted_universe must contain a `termination_date` column")

        expected = delisted_universe.filter(
            (pl.col("termination_date") >= window_start)
            & (pl.col("termination_date") <= window_end)
        )
        expected_tickers: set[str] = set(expected["ticker"].to_list())
        live_tickers: set[str] = set(live_universe["ticker"].to_list())

        if not expected_tickers:
            # No delisted tickers expected in the window — trivially passes.
            result = {
                "passed": True,
                "coverage": 1.0,
                "expected_n": 0,
                "found_n": 0,
                "missing": [],
                "note": "PASS (no delisted tickers in window)",
            }
            logger.info("survivorship_audit", **result)
            return result

        found = expected_tickers & live_tickers
        missing = sorted(expected_tickers - live_tickers)
        coverage = len(found) / len(expected_tickers)
        passed = coverage >= self.coverage_floor

        result = {
            "passed": passed,
            "coverage": coverage,
            "expected_n": len(expected_tickers),
            "found_n": len(found),
            "missing": missing,
            "note": (
                f"PASS coverage={coverage:.3f} >= floor={self.coverage_floor:.2f}"
                if passed
                else (
                    f"FAIL coverage={coverage:.3f} < floor={self.coverage_floor:.2f}; "
                    f"missing {len(missing)} delisted ticker(s)"
                )
            ),
        }
        logger.info("survivorship_audit", **{k: v for k, v in result.items() if k != "missing"})
        return result

    @staticmethod
    def raise_if_failed(result: dict) -> None:
        """Raise :class:`SurvivorshipAuditError` if ``result['passed']`` is False."""
        if not result.get("passed", False):
            raise SurvivorshipAuditError(result.get("note", "Survivorship audit failed."))

    @staticmethod
    def from_ticker_lists(
        live: Iterable[str],
        delisted: Iterable[tuple[str, date]],
    ) -> tuple[pl.DataFrame, pl.DataFrame]:
        """Convenience: build the two DataFrames from plain iterables."""
        live_df = pl.DataFrame({"ticker": list(live)})
        delisted_rows = list(delisted)
        delisted_df = pl.DataFrame(
            {
                "ticker": [t for t, _ in delisted_rows],
                "termination_date": [d for _, d in delisted_rows],
            }
        )
        return live_df, delisted_df
