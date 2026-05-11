"""Realistic execution simulator for paper trading.

Architectural guarantees:
  * ``simulate_fill()`` returns a fill price strictly on the *adverse*
    side of the quoted spread (ask for buys, bid for sells), then adds
    square-root impact.  Midpoint fills are impossible by construction.
  * Excess slippage is a linear function of ``vol_z`` and ``spread_z``
    via :data:`FRICTION_LAMBDA`.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

import polars as pl
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class FillResult:
    """Outcome of a single simulated execution."""

    fill_price: float
    slippage_bps: float
    direction: str
    impact_bps: float
    spread_bps: float
    friction_bps: float


class RealisticExecutionHarness:
    """Spread-aware paper-trade fill simulator."""

    SQRT_IMPACT_K: float = 0.1
    FRICTION_LAMBDA: float = 0.4
    VALID_DIRECTIONS: tuple[str, str] = ("buy", "sell")

    def __init__(
        self,
        sqrt_impact_k: float | None = None,
        friction_lambda: float | None = None,
    ) -> None:
        if sqrt_impact_k is not None:
            self.SQRT_IMPACT_K = sqrt_impact_k
        if friction_lambda is not None:
            self.FRICTION_LAMBDA = friction_lambda

    def simulate_fill(
        self,
        direction: str,
        bid: float,
        ask: float,
        order_size: float,
        adv: float,
        vol_z: float = 0.0,
        spread_z: float = 0.0,
    ) -> FillResult:
        """Simulate a single fill.

        Parameters
        ----------
        direction:
            ``"buy"`` or ``"sell"``.  Anything else raises ``ValueError``.
        bid, ask:
            Best bid / best ask at the moment of execution.
        order_size:
            Shares (or dollar-equivalent) of the order.
        adv:
            Average daily volume in the same units as ``order_size``.
            A small floor is applied internally so callers cannot divide
            by zero.
        vol_z, spread_z:
            Z-scored realised vol and spread friction proxies.  Both 0
            in calm regimes; positive in stress.
        """
        if direction not in self.VALID_DIRECTIONS:
            raise ValueError(
                f"direction must be one of {self.VALID_DIRECTIONS!r}; got {direction!r}"
            )
        if ask < bid:
            raise ValueError(f"ask {ask} < bid {bid}")
        if order_size <= 0:
            raise ValueError(f"order_size must be > 0; got {order_size}")

        adv_floor = max(adv, 1.0)
        midpoint = 0.5 * (bid + ask)
        spread_bps = (ask - bid) / midpoint * 1e4

        # Square-root impact (in fraction of price)
        impact_frac = self.SQRT_IMPACT_K * math.sqrt(order_size / adv_floor)
        impact_bps = impact_frac * 1e4

        # Friction-driven excess slippage in bps of price
        friction_bps = self.FRICTION_LAMBDA * (vol_z + spread_z) * spread_bps
        friction_bps = max(friction_bps, 0.0)

        if direction == "buy":
            base = ask  # adverse side of the book
            fill_price = base * (1.0 + impact_frac) + midpoint * friction_bps / 1e4
            # Guarantee adverse-side property even before impact
            assert fill_price >= ask, "buy fill must be >= ask"
        else:
            base = bid
            fill_price = base * (1.0 - impact_frac) - midpoint * friction_bps / 1e4
            assert fill_price <= bid, "sell fill must be <= bid"

        slippage_bps = abs(fill_price - midpoint) / midpoint * 1e4
        return FillResult(
            fill_price=fill_price,
            slippage_bps=slippage_bps,
            direction=direction,
            impact_bps=impact_bps,
            spread_bps=spread_bps,
            friction_bps=friction_bps,
        )

    def simulate_vwap_execution(
        self,
        direction: str,
        intraday_bars: pl.DataFrame,
        order_size: float,
        horizon_minutes: int = 20,
        vol_z: float = 0.0,
        spread_z: float = 0.0,
    ) -> dict:
        """Slice an order across ``horizon_minutes`` of intraday bars.

        Each bar must carry columns ``bid``, ``ask``, ``volume``.  If
        fewer bars than requested are available, the harness uses what
        is available and reports the actual count.
        """
        required = {"bid", "ask", "volume"}
        if not required.issubset(set(intraday_bars.columns)):
            raise ValueError(f"intraday_bars must contain columns {required}")

        n_available = intraday_bars.height
        if n_available == 0:
            raise ValueError("intraday_bars is empty")

        n_slices = min(horizon_minutes, n_available)
        if n_slices < horizon_minutes:
            logger.warning(
                "vwap_horizon_truncated",
                requested=horizon_minutes,
                available=n_available,
            )

        slice_size = order_size / n_slices
        fills: list[FillResult] = []
        total_volume_at_slice = float(intraday_bars["volume"].sum())
        adv_proxy = max(total_volume_at_slice, 1.0)
        for i in range(n_slices):
            row = intraday_bars.row(i, named=True)
            fill = self.simulate_fill(
                direction=direction,
                bid=float(row["bid"]),
                ask=float(row["ask"]),
                order_size=slice_size,
                adv=adv_proxy,
                vol_z=vol_z,
                spread_z=spread_z,
            )
            fills.append(fill)

        avg_fill = sum(f.fill_price for f in fills) / len(fills)
        avg_slippage = sum(f.slippage_bps for f in fills) / len(fills)
        return {
            "avg_fill_price": avg_fill,
            "avg_slippage_bps": avg_slippage,
            "n_slices_actual": n_slices,
            "n_slices_requested": horizon_minutes,
            "fills": fills,
        }
