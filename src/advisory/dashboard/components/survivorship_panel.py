"""Permanent, non-dismissible survivorship-bias disclosure panel.

Architecture §23 §24 mandate that this panel render at the top of
every page that displays analog distributions, win rates, or sizing
figures — and that it never offer a "don't show again" dismiss button.
This is a *structural* limitation of the V7_lite data tier.
"""
from __future__ import annotations

from typing import Any


SURVIVORSHIP_HEADLINE: str = "V7_lite — SURVIVORSHIP BIAS ACTIVE"


def render_survivorship_panel_permanent(bias_estimate: dict[str, Any]) -> None:
    """Render the permanent disclosure with an expandable detail section."""
    import streamlit as st

    st.warning(
        f"⚠️ **{SURVIVORSHIP_HEADLINE}**\n\n"
        "This system uses yfinance data.  Delisted companies are not "
        "included.  All win rates and return distributions may be "
        "overstated.\n\n"
        "Literature-estimated bias: "
        f"Sharpe +{bias_estimate['sharpe_inflation_low']}-"
        f"+{bias_estimate['sharpe_inflation_high']} | "
        f"Returns +{bias_estimate['annualized_return_inflation_low_pct']}-"
        f"+{bias_estimate['annualized_return_inflation_high_pct']}%/yr | "
        f"Win rate +{bias_estimate['win_rate_inflation_low_pp']}-"
        f"+{bias_estimate['win_rate_inflation_high_pp']} pp"
    )
    with st.expander(
        "📖 What is survivorship bias?  What can I do about it?",
        expanded=False,
    ):
        st.markdown(
            """
**What it is:** yfinance only returns data for currently-listed
companies.  Companies that went bankrupt, were delisted, or were
acquired during the historical period are missing from the analog
pool.  These are disproportionately the worst outcomes.

**Effect on this system:**

- Analog return distributions are tilted upward
- Layer 10 Kelly sizing applies a Binomial wipeout injection to
  partially correct the ES_5 term
- This is not a complete correction

**How to remove it:** Upgrade to V7 Institutional mode by subscribing
to Polygon.io and Sharadar, then setting ``APP_MODE=v7_institutional``
in ``.env``.
            """
        )
        st.caption(f"Source: {bias_estimate['source']}")
