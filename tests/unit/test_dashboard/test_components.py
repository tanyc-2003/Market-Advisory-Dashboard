"""Tests for the pure-text helpers in the dashboard components (Phase 12)."""
from __future__ import annotations

import numpy as np
import pytest

from src.advisory.dashboard.components.disagreement_banner import (
    DISAGREEMENT_OVERLAP_FLOOR,
    should_show_disagreement,
)
from src.advisory.dashboard.components.distribution_chart import (
    build_distribution_figure,
)
from src.advisory.dashboard.components.validation_badge import (
    BLOCKED_MESSAGE_TEMPLATE,
    RESEARCH_PREVIEW_HEADLINE,
    badge_emoji,
    badge_label,
)


def test_badge_label_known_statuses():
    assert badge_label("production") == "Production"
    assert badge_label("research_preview") == "Research preview"
    assert badge_label("blocked") == "Blocked"
    assert badge_label("no_report") == "No report"


def test_badge_emoji_distinct_per_status():
    emojis = {badge_emoji(s) for s in ["production", "research_preview", "blocked"]}
    assert len(emojis) == 3


def test_research_preview_headline_contains_required_phrase():
    # The architecture pins this phrase verbatim — the dashboard renders
    # it as the headline of the banner.
    assert "Research preview" in RESEARCH_PREVIEW_HEADLINE
    assert "live decision support" in RESEARCH_PREVIEW_HEADLINE


def test_blocked_message_template_carries_fields():
    msg = BLOCKED_MESSAGE_TEMPLATE.format(layer="layer1", rationale="DSR below floor")
    assert "Output hidden" in msg
    assert "layer1" in msg
    assert "DSR below floor" in msg


def test_disagreement_floor_is_70_pct():
    assert DISAGREEMENT_OVERLAP_FLOOR == 0.70


@pytest.mark.parametrize(
    "overlap, expected",
    [(0.0, True), (0.5, True), (0.69, True), (0.7, False), (1.0, False)],
)
def test_should_show_disagreement(overlap, expected):
    assert should_show_disagreement(overlap) is expected


def test_distribution_figure_includes_global_trace():
    rng = np.random.default_rng(0)
    fig = build_distribution_figure(
        global_returns=rng.normal(0, 0.02, 100),
        within_state_returns=None,
        label="AAPL",
        n_global=100,
        n_within_state=None,
    )
    # Plotly Figure exposes .data; expect at least one histogram trace.
    assert len(fig.data) >= 1
    titles = [tr.name for tr in fig.data]
    assert any("Global" in (t or "") for t in titles)


def test_distribution_figure_with_within_state_trace():
    rng = np.random.default_rng(0)
    fig = build_distribution_figure(
        global_returns=rng.normal(0, 0.02, 200),
        within_state_returns=rng.normal(0.001, 0.02, 80),
        label="AAPL",
        n_global=200,
        n_within_state=80,
    )
    titles = [tr.name for tr in fig.data]
    assert any("Within-state" in (t or "") for t in titles)
