"""Tests for select_k_oos (Phase 2)."""
from __future__ import annotations

from src.advisory.layer0_validation.audit_log import AuditLog
from src.advisory.layer1_market_state.k_selector import select_k_oos


def test_returns_best_k_in_candidates(synthetic_feature_history, feature_cols):
    log = AuditLog(":memory:")
    try:
        result = select_k_oos(
            synthetic_feature_history.head(500),
            feature_cols,
            candidate_ks=[2, 3, 4],
            audit_log=log,
        )
    finally:
        log.close()
    assert result["selected_k"] in (2, 3, 4)
    assert result["selection_reason"] == "out_of_sample_log_likelihood"


def test_audit_log_records_per_candidate(synthetic_feature_history, feature_cols):
    log = AuditLog(":memory:")
    try:
        before = log.trial_count()
        select_k_oos(
            synthetic_feature_history.head(500),
            feature_cols,
            candidate_ks=[2, 3],
            audit_log=log,
        )
        after = log.trial_count()
    finally:
        log.close()
    assert after - before >= 2
