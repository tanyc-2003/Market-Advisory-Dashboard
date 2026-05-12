"""Continuous validator — demote layers whose live PnL diverges from backtest.

V7_lite extension: a **Data Integrity Gate** runs before the existing
divergence check.  When the yfinance adapter audit indicates too many
missing or stale bars to draw conclusions, the validator returns
``VALIDATION_PAUSED_DATA_INTEGRITY`` — the layer's previous status is
preserved (no demotion).  This is a *data infrastructure* event, not an
alpha-decay signal.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import polars as pl
import structlog

from config.settings import settings

from .walk_forward import _annualised_sharpe

logger = structlog.get_logger(__name__)


@dataclass
class ContinuousValidator:
    """Compare pre-deployment Sharpe to paper-trade Sharpe.

    The architecture demands at least 90 days of paper-trade data before
    a demotion call can be made.  The divergence threshold is mode-
    dependent:

    * ``v7_institutional`` — 30% (legacy ``DIVERGENCE_THRESHOLD``).
    * ``v7_lite`` — 40% (wider to account for yfinance noise).
    """

    MIN_PAPER_TRADE_DAYS: int = 90
    DIVERGENCE_THRESHOLD: float = 0.30
    # V7_lite renamings — the original constant value stays the same;
    # we just add named aliases for clarity at the call site.
    DIVERGENCE_THRESHOLD_INSTITUTIONAL: float = 0.30
    DIVERGENCE_THRESHOLD_LITE: float = 0.40

    def _compute_live_sharpe(self, paper_trade_log: pl.DataFrame) -> float:
        if "pnl_pct" not in paper_trade_log.columns:
            raise ValueError("paper_trade_log must contain column `pnl_pct`")
        returns = np.asarray(paper_trade_log["pnl_pct"].to_list(), dtype=float)
        return _annualised_sharpe(returns)

    def evaluate(
        self,
        layer_name: str,
        pre_deployment_sharpe: float,
        paper_trade_log: pl.DataFrame,
    ) -> dict[str, Any]:
        if paper_trade_log.height < self.MIN_PAPER_TRADE_DAYS:
            return {
                "status": "INSUFFICIENT_PAPER_DATA",
                "layer": layer_name,
                "n_days": paper_trade_log.height,
                "min_required": self.MIN_PAPER_TRADE_DAYS,
                "demote_to_research": False,
            }
        live_sharpe = self._compute_live_sharpe(paper_trade_log)
        if pre_deployment_sharpe == 0:
            divergence = 0.0
        else:
            divergence = abs(live_sharpe - pre_deployment_sharpe) / abs(
                pre_deployment_sharpe
            )
        demote = divergence > self.DIVERGENCE_THRESHOLD
        result = {
            "status": "OK",
            "layer": layer_name,
            "live_sharpe": live_sharpe,
            "pre_deployment_sharpe": pre_deployment_sharpe,
            "divergence": divergence,
            "divergence_threshold": self.DIVERGENCE_THRESHOLD,
            "demote_to_research": demote,
        }
        logger.info("continuous_validator", **result)
        return result

    def should_demote(
        self,
        layer_name: str,
        pre_deployment_sharpe: float,
        paper_trade_log: pl.DataFrame,
    ) -> bool:
        return bool(
            self.evaluate(layer_name, pre_deployment_sharpe, paper_trade_log)[
                "demote_to_research"
            ]
        )

    # ------------------------------------------------------------------ #
    # V7_lite extensions — additive
    # ------------------------------------------------------------------ #

    def _data_integrity_check(
        self,
        paper_trade_log: pl.DataFrame,
        adapter_audit: pl.DataFrame,
    ) -> dict[str, Any]:
        """V7_lite Data Integrity Gate.

        Returns ``{"integrity_ok": bool, "reasons": [...], ...}``.  Two
        failure modes:

        * ``missing_bars_fraction`` exceeds
          :data:`settings.max_missing_bar_fraction` — too many tickers
          reported MISSING in the audit log.
        * ``stale_cross_ticker_fraction`` exceeds
          :data:`settings.max_stale_cross_ticker_fraction` — a single
          fetch date had more stale (zero-row) tickers than the
          architecturally pinned ceiling, suggesting a scraper outage.
        """
        reasons: list[str] = []
        if adapter_audit is None or adapter_audit.is_empty():
            return {
                "integrity_ok": True,
                "missing_bars_fraction": 0.0,
                "stale_cross_ticker_fraction": 0.0,
                "reasons": ["adapter_audit empty — gate inactive"],
            }

        n_total = adapter_audit.height
        missing_n = adapter_audit.filter(pl.col("status") == "MISSING").height
        missing_frac = missing_n / n_total if n_total else 0.0

        # Cross-ticker staleness: per fetch_date, count zero-row tickers.
        stale_frac = 0.0
        if "fetch_date" in adapter_audit.columns:
            grouped = (
                adapter_audit
                .group_by("fetch_date")
                .agg(
                    pl.len().alias("n"),
                    pl.col("n_rows").eq(0).sum().alias("n_stale"),
                )
                .with_columns(
                    (pl.col("n_stale") / pl.col("n")).alias("stale_frac")
                )
            )
            if grouped.height:
                stale_frac = float(grouped["stale_frac"].max() or 0.0)

        if missing_frac > settings.max_missing_bar_fraction:
            reasons.append(
                f"missing-bar fraction {missing_frac:.3f} > "
                f"{settings.max_missing_bar_fraction:.3f}"
            )
        if stale_frac > settings.max_stale_cross_ticker_fraction:
            reasons.append(
                f"cross-ticker stale fraction {stale_frac:.3f} > "
                f"{settings.max_stale_cross_ticker_fraction:.3f}"
            )

        return {
            "integrity_ok": not reasons,
            "missing_bars_fraction": missing_frac,
            "stale_cross_ticker_fraction": stale_frac,
            "reasons": reasons,
        }

    def reassess(
        self,
        layer_name: str,
        pre_deployment_sharpe: float,
        paper_trade_log: pl.DataFrame,
        adapter_audit: pl.DataFrame | None = None,
        app_mode: str = "v7_lite",
    ) -> dict[str, Any]:
        """V7_lite-aware reassessment.

        Pipeline:

        1. If ``app_mode == "v7_lite"`` and an ``adapter_audit`` frame
           is provided, run :meth:`_data_integrity_check`.  On failure
           return ``VALIDATION_PAUSED_DATA_INTEGRITY`` — no demotion.
        2. Otherwise run the existing :meth:`evaluate` logic with the
           mode-appropriate divergence threshold.
        """
        if app_mode == "v7_lite" and adapter_audit is not None:
            integrity = self._data_integrity_check(paper_trade_log, adapter_audit)
            if not integrity["integrity_ok"]:
                logger.info(
                    "validation_paused_data_integrity",
                    layer=layer_name,
                    reasons=integrity["reasons"],
                )
                return {
                    "status": "VALIDATION_PAUSED_DATA_INTEGRITY",
                    "layer": layer_name,
                    "reasons": integrity["reasons"],
                    "missing_bars_fraction": integrity["missing_bars_fraction"],
                    "stale_cross_ticker_fraction": integrity[
                        "stale_cross_ticker_fraction"
                    ],
                    "demote_to_research": False,
                }

        # Run the standard divergence check with the mode-appropriate threshold.
        threshold = (
            self.DIVERGENCE_THRESHOLD_LITE
            if app_mode == "v7_lite"
            else self.DIVERGENCE_THRESHOLD_INSTITUTIONAL
        )
        # Temporarily swap the threshold so we don't have to duplicate logic.
        original = self.DIVERGENCE_THRESHOLD
        try:
            self.DIVERGENCE_THRESHOLD = threshold
            result = self.evaluate(layer_name, pre_deployment_sharpe, paper_trade_log)
        finally:
            self.DIVERGENCE_THRESHOLD = original
        result["app_mode"] = app_mode
        return result
