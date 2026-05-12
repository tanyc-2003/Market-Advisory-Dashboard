"""V7_lite sizing diagnostics — survivorship-bias aware Kelly.

Why the **binomial draw**, not a deterministic floor:

> "A deterministic floor of 1 wipeout for n=50 analogs with a 10-day
> hold implies a per-10-day wipeout rate of 2%, which annualises to
> ~52%. That is 26× the true rate and would choke Kelly to near-zero
> on all trades. The Binomial draw correctly reflects that wipeouts
> are rare per short window: with n=50 and p=0.000794, 96% of draws
> return 0."

This is also why ``SURVIVORSHIP_WIN_RATE_ADJUSTMENT`` is **forbidden** —
it modifies the wrong Kelly term and is replaced by tail-aware
injection into the ES_5 calculation.

The wrapper :func:`sizing_diagnostics_lite` injects wipeouts into the
analog distribution, then defers to the existing
:func:`~src.advisory.layer10_sizing.diagnostics.sizing_diagnostics` so
all the architectural invariants (tail-aware Kelly, regime haircut,
absolute cap) continue to apply automatically.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import structlog

from config.settings import settings

from .diagnostics import sizing_diagnostics

logger = structlog.get_logger(__name__)


def inject_synthetic_wipeouts(
    analog_returns: np.ndarray,
    annual_impairment_rate: float | None = None,
    period_days: int = 10,
    synthetic_wipeout_return: float | None = None,
    rng: np.random.Generator | None = None,
) -> tuple[np.ndarray, int]:
    """Inject ``Binomial(n, p)`` synthetic wipeouts into the analog pool.

    Parameters
    ----------
    analog_returns:
        Forward-return samples drawn from the survivor-only analog set.
    annual_impairment_rate:
        Annual probability that a randomly-selected listed company
        suffers a permanent impairment (delisting / bankruptcy /
        catastrophic single-name event).  Default reads from settings.
    period_days:
        Hold period of the strategy in trading days.  The per-period
        rate is ``annual_impairment_rate * period_days / 252``.
    synthetic_wipeout_return:
        Return value injected for each drawn wipeout.  Default reads
        from settings (``-0.60`` — conservative severe-impairment floor).
    rng:
        ``np.random.default_rng(seed=...)`` for reproducibility in tests.
        Production callers pass a freshly-seeded generator each run.

    Returns
    -------
    (augmented_returns, n_injected) tuple — augmented array equal to
    ``analog_returns`` plus ``n_injected`` synthetic-wipeout entries.
    """
    arr = np.asarray(analog_returns, dtype=float)
    if rng is None:
        rng = np.random.default_rng()
    rate = (
        annual_impairment_rate
        if annual_impairment_rate is not None
        else settings.annual_impairment_rate
    )
    wipeout_value = (
        synthetic_wipeout_return
        if synthetic_wipeout_return is not None
        else settings.synthetic_wipeout_return
    )
    p = rate * period_days / 252.0
    n_injected = int(rng.binomial(arr.size, p))
    if n_injected == 0:
        return arr, 0
    injected = np.full(n_injected, wipeout_value, dtype=float)
    return np.concatenate([arr, injected]), n_injected


def sizing_diagnostics_lite(
    analog_returns: np.ndarray,
    state_uncertainty: float,
    hmm_analog_overlap_pct: float,
    base_kelly_haircut: float = 0.50,
    period_days: int = 10,
    rng: np.random.Generator | None = None,
) -> dict[str, Any]:
    """V7_lite sizing wrapper around
    :func:`~src.advisory.layer10_sizing.diagnostics.sizing_diagnostics`.

    Inject wipeouts → call the canonical diagnostic → append the
    survivorship bias note.  The wrapper does not duplicate Kelly
    arithmetic; the architectural invariants are inherited.
    """
    augmented, n_injected = inject_synthetic_wipeouts(
        analog_returns, period_days=period_days, rng=rng
    )
    result = sizing_diagnostics(
        analog_returns=augmented,
        state_uncertainty=state_uncertainty,
        hmm_analog_overlap_pct=hmm_analog_overlap_pct,
        base_kelly_haircut=base_kelly_haircut,
    )
    note = (
        "V7_lite survivorship correction applied: "
        f"{n_injected} synthetic wipeout(s) at {settings.synthetic_wipeout_return:+.2f} "
        f"(Binomial draw at annual_rate={settings.annual_impairment_rate:.3f}, "
        f"period_days={period_days}).  This partially offsets the upward "
        "tilt in win rates from the survivor-only yfinance analog pool."
    )
    result["n_injected"] = n_injected
    result["survivorship_bias_note"] = note
    result["app_mode"] = "v7_lite"
    logger.info(
        "sizing_lite", n_injected=n_injected, displayed_kelly=result.get("displayed_kelly")
    )
    return result
