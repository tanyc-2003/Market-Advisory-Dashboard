"""Confidence language tiers — calibrated to sample size + Wilson CI."""
from __future__ import annotations

CONFIDENCE_LANGUAGE: dict[str, str] = {
    "strong": (
        "Strong evidence: {n} analogs, hit rate {hit_rate:.0%} "
        "(Wilson 95% CI lower bound {ci_low:.0%})."
    ),
    "moderate": (
        "Moderate evidence: {n} analogs, hit rate {hit_rate:.0%} "
        "(Wilson 95% CI lower bound {ci_low:.0%})."
    ),
    "weak": (
        "Weak evidence: {n} analogs, hit rate {hit_rate:.0%} "
        "(Wilson 95% CI lower bound {ci_low:.0%}) — sample size or CI does "
        "not support a confident claim."
    ),
    "insufficient": (
        "Insufficient evidence: only {n} analogs available; no confident "
        "statement possible."
    ),
}


def get_confidence_language(n: int, hit_rate: float, ci_low: float) -> str:
    """Pick a tier and format the template."""
    if n < 15:
        tier = "insufficient"
    elif n >= 50 and ci_low >= 0.55:
        tier = "strong"
    elif n >= 25 and ci_low >= 0.50:
        tier = "moderate"
    else:
        tier = "weak"
    return CONFIDENCE_LANGUAGE[tier].format(n=n, hit_rate=hit_rate, ci_low=ci_low)
