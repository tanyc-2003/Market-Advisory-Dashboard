"""Tests for FDR correction + top-K filtering (Phase 8)."""
from __future__ import annotations

from unittest.mock import patch

from src.advisory.layer7_hygiene.fdr import (
    SEVERITY_SCORES,
    apply_fdr_correction,
    filter_top_k_alerts,
)


def test_by_method_is_used():
    alerts = [
        {"alert_type": "contradiction", "p_value": 0.001},
        {"alert_type": "contradiction", "p_value": 0.04},
    ]
    with patch(
        "src.advisory.layer7_hygiene.fdr.multipletests",
        return_value=([True, False], [0.005, 0.08], 0.0, 0.0),
    ) as mock:
        apply_fdr_correction(alerts)
    _, kwargs = mock.call_args
    assert kwargs.get("method") == "fdr_by"


def test_alerts_without_p_value_pass_through():
    alerts = [
        {"alert_type": "factor_redundancy"},
        {"alert_type": "contradiction", "p_value": 0.001},
    ]
    survivors = apply_fdr_correction(alerts)
    # The plain alert must remain.
    assert any("p_value" not in a for a in survivors)


def test_surviving_alerts_have_corrected_p():
    alerts = [{"alert_type": "contradiction", "p_value": 1e-9}]
    survivors = apply_fdr_correction(alerts)
    assert all("p_value_corrected" in a for a in survivors)


def test_top_k_returns_highest_severity_first():
    alerts = [
        {"alert_type": "friction_anomaly"},
        {"alert_type": "contradiction", "p_value_corrected": 0.001},
        {"alert_type": "factor_redundancy"},
        {"alert_type": "regime_disagreement"},
        {"alert_type": "transition_signal"},
    ]
    top3 = filter_top_k_alerts(alerts, k=3)
    severities = [SEVERITY_SCORES[a["alert_type"]] for a in top3]
    assert severities == sorted(severities, reverse=True)


def test_empty_alert_list_returns_empty():
    assert apply_fdr_correction([]) == []
    assert filter_top_k_alerts([], k=5) == []
