"""Tail-aware Kelly diagnostics, regime-haircut, and 20% absolute cap.

Three structural properties enforced (architecture §15):

1. **Tail-aware Kelly.** The loss term is the absolute value of the 5th
   percentile (Expected Shortfall, ES₅) of the analog return distribution,
   not the arithmetic mean of losses. On small heavy-tailed samples, the
   mean of negative returns understates the true expected loss because a
   few rare large losses dominate the population mean; using |ES₅|
   targets the tail directly.

2. **Regime-adjusted haircut.** The haircut multiplier is::

       effective_haircut = base_kelly_haircut
                           * (1 - state_uncertainty)
                           * min(1.0, hmm_analog_overlap_pct * 1.5)

   When ``state_uncertainty == 1.0`` and ``hmm_analog_overlap_pct == 0.0``
   this yields zero, producing a *displayed Kelly of zero*.  We do not
   floor at a non-zero minimum — zero confidence must produce zero
   displayed size.

3. **Absolute cap.** Every Kelly variant is clamped to
   :data:`KELLY_ABSOLUTE_CAP`.  No output ever exceeds it.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger(__name__)


KELLY_ABSOLUTE_CAP: float = 0.20
KELLY_LOW_SAMPLE_THRESHOLD: int = 100
ES_QUANTILE: float = 0.05
MIN_ANALOGS: int = 30
DEFAULT_BASE_HAIRCUT: float = 0.50


SIZING_NOTE: str = (
    "These are diagnostic computations, not recommendations. Kelly uses "
    "|ES₅| as the loss term to be tail-aware, is capped at 20%, and "
    "is haircut by regime uncertainty and HMM/Analog disagreement."
)


def _cap(value: float) -> float:
    """Clamp a Kelly fraction to ``[0, KELLY_ABSOLUTE_CAP]``."""
    if not np.isfinite(value):
        return 0.0
    return float(max(0.0, min(KELLY_ABSOLUTE_CAP, value)))


def sizing_diagnostics(
    analog_returns: np.ndarray | list[float],
    state_uncertainty: float,
    hmm_analog_overlap_pct: float,
    base_kelly_haircut: float = DEFAULT_BASE_HAIRCUT,
) -> dict[str, Any]:
    """Compute the four Kelly variants from an analog return distribution.

    Parameters
    ----------
    analog_returns:
        Forward-return samples drawn from Layer 2's analog set.
    state_uncertainty:
        ``1 - max(state_probs)`` from Layer 1.  Range ``[0, 1]``.
    hmm_analog_overlap_pct:
        Overlap fraction from
        :class:`HistoricalAnalogEngine.find_analogs_with_disagreement`.
    base_kelly_haircut:
        Multiplicative haircut applied *before* regime adjustment.
        Default ``0.5`` (half-Kelly).

    Returns
    -------
    dict with keys ``raw_kelly``, ``haircut_kelly_standard``,
    ``haircut_kelly_regime``, ``displayed_kelly``, plus diagnostics.
    Returns ``{"status": "INSUFFICIENT_ANALOGS", ...}`` when fewer than
    :data:`MIN_ANALOGS` analogs are supplied.
    """
    arr = np.asarray(list(analog_returns), dtype=float)
    arr = arr[np.isfinite(arr)]
    n = arr.size

    if n < MIN_ANALOGS:
        return {
            "status": "INSUFFICIENT_ANALOGS",
            "n": int(n),
            "min_required": MIN_ANALOGS,
            "note": SIZING_NOTE,
        }

    warnings: list[str] = []

    if n < KELLY_LOW_SAMPLE_THRESHOLD:
        warnings.append(
            f"Sample fragile: {n} analogs < threshold {KELLY_LOW_SAMPLE_THRESHOLD}; "
            "treat magnitudes with extra scepticism."
        )

    wins_mask = arr > 0
    losses_mask = arr < 0
    n_wins = int(wins_mask.sum())
    win_rate = float(n_wins / n)

    if n_wins == 0 or not wins_mask.any():
        # No upside in the sample — Kelly diagnostic is identically zero.
        result = {
            "status": "OK",
            "n": int(n),
            "win_rate": win_rate,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "es_5": 0.0,
            "raw_kelly": 0.0,
            "haircut_kelly_standard": 0.0,
            "haircut_kelly_regime": 0.0,
            "displayed_kelly": 0.0,
            "effective_haircut": 0.0,
            "base_kelly_haircut": float(base_kelly_haircut),
            "kelly_absolute_cap": KELLY_ABSOLUTE_CAP,
            "warnings": warnings + ["No winning analogs in sample."],
            "note": SIZING_NOTE,
        }
        return result

    avg_win = float(arr[wins_mask].mean())
    es_5 = float(np.quantile(arr, ES_QUANTILE))

    if es_5 >= 0:
        # No downside tail; fall back to mean of negative returns if any.
        if losses_mask.any():
            avg_loss = float(abs(arr[losses_mask].mean()))
            logger.warning(
                "sizing_no_downside_tail_using_mean_loss",
                n=n,
                es_5=es_5,
                avg_loss_used=avg_loss,
            )
        else:
            # No losses at all — Kelly's denominator is zero, output zero.
            return {
                "status": "OK",
                "n": int(n),
                "win_rate": win_rate,
                "avg_win": avg_win,
                "avg_loss": 0.0,
                "es_5": es_5,
                "raw_kelly": 0.0,
                "haircut_kelly_standard": 0.0,
                "haircut_kelly_regime": 0.0,
                "displayed_kelly": 0.0,
                "effective_haircut": 0.0,
                "base_kelly_haircut": float(base_kelly_haircut),
                "kelly_absolute_cap": KELLY_ABSOLUTE_CAP,
                "warnings": warnings
                + [
                    "Analog distribution has no negative tail — Kelly "
                    "undefined; displayed as 0.0."
                ],
                "note": SIZING_NOTE,
            }
        warnings.append(
            f"Analog ES₅ is non-negative ({es_5:.4f}); falling back to "
            "mean of negative returns for Kelly loss term."
        )
    else:
        avg_loss = float(abs(es_5))

    payoff_ratio = avg_win / avg_loss if avg_loss > 0 else 0.0
    if payoff_ratio <= 0:
        raw_kelly = 0.0
    else:
        # Classical Kelly: f = p - (1 - p) / R
        raw_kelly_signed = win_rate - (1.0 - win_rate) / payoff_ratio
        raw_kelly = max(0.0, raw_kelly_signed)

    haircut_kelly_standard = _cap(raw_kelly * base_kelly_haircut)

    # Clamp inputs into [0, 1] defensively
    state_unc_clamped = float(max(0.0, min(1.0, state_uncertainty)))
    overlap_clamped = float(max(0.0, min(1.0, hmm_analog_overlap_pct)))

    effective_haircut = (
        base_kelly_haircut
        * (1.0 - state_unc_clamped)
        * min(1.0, overlap_clamped * 1.5)
    )
    haircut_kelly_regime = _cap(raw_kelly * effective_haircut)

    displayed_kelly = haircut_kelly_regime  # the dashboard surface

    return {
        "status": "OK",
        "n": int(n),
        "win_rate": win_rate,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "es_5": es_5,
        "payoff_ratio": payoff_ratio,
        "raw_kelly": _cap(raw_kelly),
        "haircut_kelly_standard": haircut_kelly_standard,
        "haircut_kelly_regime": haircut_kelly_regime,
        "displayed_kelly": displayed_kelly,
        "effective_haircut": effective_haircut,
        "base_kelly_haircut": float(base_kelly_haircut),
        "state_uncertainty": state_unc_clamped,
        "hmm_analog_overlap_pct": overlap_clamped,
        "kelly_absolute_cap": KELLY_ABSOLUTE_CAP,
        "warnings": warnings,
        "note": SIZING_NOTE,
    }
