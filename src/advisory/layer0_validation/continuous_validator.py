"""Continuous validator — demote layers whose live PnL diverges from backtest."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import polars as pl
import structlog

from .walk_forward import _annualised_sharpe

logger = structlog.get_logger(__name__)


@dataclass
class ContinuousValidator:
    """Compare pre-deployment Sharpe to paper-trade Sharpe.

    The architecture demands at least 90 days of paper-trade data before
    a demotion call can be made, and a 30% relative divergence threshold.
    """

    MIN_PAPER_TRADE_DAYS: int = 90
    DIVERGENCE_THRESHOLD: float = 0.30

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
