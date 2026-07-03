"""Tier 2 #4 — bull / bear case synthesis.

Composes signals the dashboard already computes (drivers, hit rate, distribution
skew, regime alignment, disagreement, thin samples) into a side-by-side
case-for / case-against with a plain-language verdict + confidence. No new model;
it mutates each asset dict, adding a ``case`` field.
"""
from __future__ import annotations

from typing import Any


def build_cases(assets: list[dict[str, Any]], market_state: dict[str, Any]) -> None:
    """Attach `case` to each asset in place."""
    states = (market_state or {}).get("states") or []
    dominant = states[0]["name"] if states else ""
    regime_bull = "Bull" in dominant
    regime_bear = "Bear" in dominant

    for a in assets:
        bull: list[str] = []
        bear: list[str] = []

        for d in a.get("drivers", []):
            (bull if "↑" in d else bear).append(d)

        hit = a.get("hitRate", 0.0)
        (bull if hit > 0.5 else bear).append(f"hit rate {hit * 100:.0f}%")

        p5, p50, p95 = a.get("p5", 0.0), a.get("p50", 0.0), a.get("p95", 0.0)
        if p50 > 0 and p95 > abs(p5):
            bull.append("right-skewed forward distribution")
        elif abs(p5) > p95:
            bear.append("large downside tail")

        if regime_bull:
            bull.append(f"regime: {dominant}")
        elif regime_bear:
            bear.append(f"regime: {dominant}")

        if a.get("disagreement"):
            bear.append("regime-conditioning disagreement")

        n = a.get("n", 0)
        if n < 15:
            bear.append(f"thin analog set (n={n})")

        if a.get("sizing", {}).get("displayed", 0.0) > 0:
            bull.append(f"positive Kelly ({a['sizing']['displayed']:.2f})")

        net = len(bull) - len(bear)
        verdict = "lean long" if net >= 2 else "lean short" if net <= -2 else "neutral"

        a["case"] = {
            "bull": bull,
            "bear": bear,
            "verdict": verdict,
            "confidence": a.get("conf", "insufficient"),
        }
