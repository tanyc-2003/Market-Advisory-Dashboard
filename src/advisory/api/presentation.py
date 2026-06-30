"""Server-side representative dashboard data.

This is the single source of truth for the layer outputs the quant pipeline
does not yet materialise (market state, analogs, sizing ladders, calibration,
stress scenarios, alerts). Values are ported verbatim from the approved design
mock so the dashboard renders identically until each section is swapped for
live compute.

Every function returns plain JSON-safe structures with **camelCase** keys that
match the frontend's TypeScript types exactly, so FastAPI can return them with
no transformation layer.
"""
from __future__ import annotations

from typing import Any

# Snapshot label shown in the sidebar when no live feature date is available.
AS_OF = "Jun 27, 2026"

SIZING_NOTE = (
    "Tail-aware Kelly using 5th-percentile expected shortfall as the loss term, "
    "haircut for state uncertainty and analog disagreement, then hard-capped at "
    "20%. A diagnostic — not a recommendation."
)

STRESS_NOTE = (
    "Shocks applied to fitted factor betas under a two-regime covariance (MCD "
    "with Ledoit-Wolf fallback). Historical analogy, not a forecast."
)

CALIBRATION_DRIFT = (
    "4 invalidated-and-lost trades in the last 30 days exceeds the threshold of "
    "3 — high-confidence calls are not surviving contact with the market."
)


def layers() -> list[dict[str, Any]]:
    return [
        {"id": "L0", "name": "Validation", "status": "production", "sharpe": None, "ece": None, "p30": None, "dsr": 0.97, "rationale": "All five sign-off criteria pass."},
        {"id": "L1", "name": "Market State", "status": "production", "sharpe": 0.71, "ece": 0.041, "p30": 0.18, "dsr": 0.96, "rationale": "HMM passes walk-forward, calibration and deflated-Sharpe floors."},
        {"id": "L2", "name": "Analogs", "status": "research_preview", "sharpe": 0.58, "ece": 0.044, "p30": 0.05, "dsr": 0.81, "rationale": "Deflated Sharpe 0.81 < 0.95 floor — predictive edge not yet distinguishable from trial count."},
        {"id": "L3", "name": "Attribution", "status": "research_preview", "sharpe": 0.55, "ece": 0.071, "p30": 0.07, "dsr": 0.95, "rationale": "ECE 0.071 > 0.05 ceiling — SHAP-driven probabilities slightly overconfident."},
        {"id": "L4", "name": "Risk Model", "status": "production", "sharpe": 0.63, "ece": 0.038, "p30": 0.11, "dsr": 0.96, "rationale": "Factor exposures and tail betas validated."},
        {"id": "L5", "name": "Stress Monitor", "status": "production", "sharpe": None, "ece": None, "p30": None, "dsr": None, "rationale": "Friction z-scores; calendar suppression active. No predictive gate required."},
        {"id": "L6", "name": "Portfolio", "status": "research_preview", "sharpe": 0.52, "ece": 0.043, "p30": -0.04, "dsr": 0.95, "rationale": "CPCV 30th-percentile Sharpe -0.04 < 0.0 floor — harsh-path performance is negative."},
        {"id": "L7", "name": "Hygiene", "status": "production", "sharpe": 0.66, "ece": 0.039, "p30": 0.09, "dsr": 0.96, "rationale": "Contradiction tests pass Fisher exact + FDR-BY correction."},
        {"id": "L8", "name": "Journal", "status": "production", "sharpe": None, "ece": None, "p30": None, "dsr": None, "rationale": "Data layer — trade record store. No predictive gate."},
        {"id": "L9", "name": "Calibration", "status": "research_preview", "sharpe": None, "ece": 0.061, "p30": None, "dsr": None, "rationale": "ECE 0.061 > 0.05 and only 21 graded entries — near the 15-entry minimum."},
        {"id": "L10", "name": "Sizing", "status": "research_preview", "sharpe": 0.58, "ece": 0.044, "p30": 0.05, "dsr": 0.81, "rationale": "Inherits research-preview status from Layer 2 analog returns."},
    ]


def market_state() -> dict[str, Any]:
    return {
        "states": [
            {"name": "Calm Bull", "prob": 0.57},
            {"name": "Volatile Bull", "prob": 0.22},
            {"name": "Neutral / transition", "prob": 0.12},
            {"name": "Calm Bear", "prob": 0.06},
            {"name": "Stressed Bear", "prob": 0.03},
        ],
        "uncertainty": "0.41",
        "transition": (
            "Elevated probability of transition into Volatile Bull (0.22). "
            "Term-structure and realized-vol channels are the main contributors; "
            "treat regime persistence as the base case, not a certainty."
        ),
    }


def assets() -> list[dict[str, Any]]:
    return [
        {"ticker": "NVDA", "sector": "Semiconductors", "n": 34, "hitRate": 0.62, "conf": "moderate",
         "p5": -0.084, "p25": -0.021, "p50": 0.018, "p75": 0.057, "p95": 0.121, "disagreement": False,
         "drivers": ["realized_vol_21d ↑", "ret_63d ↑", "rsi_14 ↑"],
         "sizing": {"raw": 0.34, "std": 0.17, "regime": 0.11, "displayed": 0.11}},
        {"ticker": "MSFT", "sector": "Software", "n": 41, "hitRate": 0.58, "conf": "moderate",
         "p5": -0.061, "p25": -0.012, "p50": 0.014, "p75": 0.041, "p95": 0.083, "disagreement": False,
         "drivers": ["ret_21d ↑", "pct_above_ma50 ↑", "realized_vol_21d ↓"],
         "sizing": {"raw": 0.22, "std": 0.13, "regime": 0.09, "displayed": 0.09}},
        {"ticker": "XOM", "sector": "Energy", "n": 19, "hitRate": 0.53, "conf": "weak",
         "p5": -0.093, "p25": -0.031, "p50": 0.004, "p75": 0.043, "p95": 0.108, "disagreement": True,
         "disagreementNote": "Global vs within-state analogs overlap only 41% — regime conditioning materially changes the picture.",
         "drivers": ["ret_5d ↓", "realized_vol_21d ↑", "rsi_14 ↓"],
         "sizing": {"raw": 0.09, "std": 0.06, "regime": 0.04, "displayed": 0.04}},
        {"ticker": "JPM", "sector": "Financials", "n": 28, "hitRate": 0.60, "conf": "moderate",
         "p5": -0.058, "p25": -0.014, "p50": 0.012, "p75": 0.038, "p95": 0.079, "disagreement": False,
         "drivers": ["ret_63d ↑", "pct_above_ma50 ↑", "ret_1d ↑"],
         "sizing": {"raw": 0.18, "std": 0.11, "regime": 0.08, "displayed": 0.08}},
        {"ticker": "TSLA", "sector": "Auto", "n": 12, "hitRate": 0.50, "conf": "insufficient",
         "p5": -0.142, "p25": -0.048, "p50": -0.002, "p75": 0.061, "p95": 0.171, "disagreement": True,
         "disagreementNote": "Only 12 effective analogs and 38% overlap — distribution is too wide to read as evidence.",
         "drivers": ["realized_vol_21d ↑", "ret_5d ↓", "rsi_14 ↓"],
         "sizing": {"raw": 0.04, "std": 0.03, "regime": 0.02, "displayed": 0.02}},
    ]


def alerts() -> list[dict[str, Any]]:
    return [
        {"sev": 3, "title": "Validated contradiction — momentum vs term structure", "detail": "Bullish 63-day momentum co-occurs with an inverted yield-curve slope. Fisher exact p < 0.01, survives FDR-BY."},
        {"sev": 2, "title": "Factor redundancy across watchlist", "detail": "The market factor explains ≥ 50% of attribution for 4 of 5 names — positions are less diversified than they appear."},
        {"sev": 1, "title": "Calendar event ahead", "detail": "FOMC day inside the 10-day horizon. Friction monitor suppresses intraday alerts on the event day itself."},
    ]


def unknowns() -> list[str]:
    return [
        "Forward returns are conditional on regime persistence. A regime break invalidates the analog set without warning.",
        "Two watchlist names have fewer than 20 effective analogs — their distributions are shown but should not be read as evidence.",
        "Attribution is correlational. SHAP values explain the model, not the market.",
        "The system cannot detect structural change until after it has happened.",
    ]


def portfolio() -> dict[str, Any]:
    return {
        "weights": [
            {"ticker": "NVDA", "w": 0.18},
            {"ticker": "MSFT", "w": 0.15},
            {"ticker": "JPM", "w": 0.12},
            {"ticker": "XOM", "w": 0.10},
            {"ticker": "AMD", "w": 0.09},
            {"ticker": "Cash", "w": 0.36},
        ],
        "effectiveN": "3.4",
        "scenarios": ["2008 Credit Crisis", "2011 EU Debt", "2020 COVID Crash", "2022 Rate Shock"],
        "stressMap": {
            "2008 Credit Crisis": {"vol": 0.41, "base": 0.17, "factors": [["Equity beta", "-31.2%"], ["Credit (HY) spread", "-14.8%"], ["Volatility", "+22.0%"]]},
            "2011 EU Debt": {"vol": 0.33, "base": 0.17, "factors": [["Equity beta", "-19.4%"], ["Rates (TLT)", "+6.1%"], ["Volatility", "+15.5%"]]},
            "2020 COVID Crash": {"vol": 0.48, "base": 0.17, "factors": [["Equity beta", "-34.0%"], ["Volatility", "+28.3%"], ["Commodity", "-12.6%"]]},
            "2022 Rate Shock": {"vol": 0.29, "base": 0.17, "factors": [["Rates (TLT)", "-17.9%"], ["Growth / QQQ", "-21.4%"], ["USD (UUP)", "+5.2%"]]},
        },
        "stressNote": STRESS_NOTE,
        "cluster": {"members": "NVDA + AMD"},
    }


def journal() -> dict[str, Any]:
    """Representative journal shown before any real entries are logged."""
    return {
        "open": [
            {"ticker": "NVDA", "direction": "long", "conf": 4, "thesis": "Calm-bull regime + strong 63d momentum; invalidates on vol regime break.", "opened": "Jun 18"},
            {"ticker": "XOM", "direction": "short", "conf": 2, "thesis": "Weak analogs, low conviction; sized small. Invalidates above MA50.", "opened": "Jun 23"},
            {"ticker": "JPM", "direction": "long", "conf": 3, "thesis": "Financials breadth improving; cut if curve re-inverts hard.", "opened": "Jun 25"},
        ],
        "closed": [
            {"ticker": "MSFT", "direction": "long", "outcome": "Thesis confirmed — held 12d", "pnl": "+4.2%"},
            {"ticker": "TSLA", "direction": "long", "outcome": "Invalidated — vol spike, cut early", "pnl": "-3.1%"},
            {"ticker": "AAPL", "direction": "avoided", "outcome": "Sat out — insufficient analogs", "pnl": "—"},
        ],
    }


def calibration() -> dict[str, Any]:
    return {
        "cards": [
            {"label": "Brier score", "value": "0.214", "note": "Lower is better. 0.25 = coin flip."},
            {"label": "Expected calibration error", "value": "0.061", "note": "Above the 0.05 ceiling — mild overconfidence."},
            {"label": "Graded entries", "value": "21", "note": "Above the 15-entry minimum, below comfort."},
        ],
        "rows": [
            {"band": "1", "implied": 0.30, "observed": 0.34, "lo": 0.10, "hi": 0.62, "n": 3},
            {"band": "2", "implied": 0.45, "observed": 0.40, "lo": 0.18, "hi": 0.67, "n": 4},
            {"band": "3", "implied": 0.55, "observed": 0.50, "lo": 0.27, "hi": 0.73, "n": 6},
            {"band": "4", "implied": 0.70, "observed": 0.60, "lo": 0.31, "hi": 0.83, "n": 5},
            {"band": "5", "implied": 0.85, "observed": 0.67, "lo": 0.30, "hi": 0.90, "n": 3},
        ],
        "drift": CALIBRATION_DRIFT,
    }


# Representative fallbacks for the genuinely-real Validation summaries, used
# only when the DuckDB stores are absent.
SURVIVORSHIP_COVERAGE_FALLBACK = "0.971"
DSR_TRIALS_FALLBACK = "3,184"
