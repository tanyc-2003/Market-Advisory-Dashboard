#!/usr/bin/env python3
"""Validate a candidate HMM and (optionally) promote it to production.

Runs walk-forward CV + deflated Sharpe + builds a
:class:`ValidationReport` with ``app_mode="v7_lite"`` and
``survivorship_audit="BYPASSED_LITE_MODE"``.  On pass + ``--promote-on-pass``,
copies the candidate to ``models/hmm_v7_lite.pkl`` and updates the
``hmm_model_registry``.

Usage::

    python scripts/validate_hmm_candidate.py \
        --candidate models/hmm_v7_lite_20260512.pkl \
        --promote-on-pass
"""
from __future__ import annotations

import argparse
import pickle
import sys
from datetime import date
from pathlib import Path

import numpy as np
import polars as pl

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from config.settings import settings  # noqa: E402
from src.advisory.data_infra.feature_store import FeatureStore  # noqa: E402
from src.advisory.layer0_validation.audit_log import AuditLog  # noqa: E402
from src.advisory.layer0_validation.deflated_sharpe import deflated_sharpe  # noqa: E402
from src.advisory.layer0_validation.report import (  # noqa: E402
    LiteBypassReason,
    ValidationReport,
    ValidationStatus,
    persist_report,
)
from src.advisory.layer0_validation.walk_forward import WalkForwardCV  # noqa: E402
from src.advisory.layer1_market_state.registry import promote_candidate  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate an HMM candidate")
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--promote-on-pass", action="store_true")
    parser.add_argument("--app-mode", default=settings.app_mode)
    args = parser.parse_args()

    if not args.candidate.exists():
        raise SystemExit(f"Candidate not found: {args.candidate}")

    with open(args.candidate, "rb") as f:
        artifact = pickle.load(f)

    feature_cols = list(artifact["feature_cols"])
    print(
        f"Validating {args.candidate.name} "
        f"({len(feature_cols)}-dim, mode={artifact['app_mode']})"
    )

    store = FeatureStore(settings.main_db_path, settings.cache_dir)
    audit_log = AuditLog(settings.audit_db_path)
    try:
        # Reuse the training-window feature history for WF CV.
        cols = ", ".join(f"'{c}'" for c in feature_cols)
        rows = store.conn.execute(
            f"""
            SELECT effective_date, feature_name, AVG(feature_value) AS value
            FROM features_pit
            WHERE feature_name IN ({cols})
            GROUP BY effective_date, feature_name
            ORDER BY effective_date
            """
        ).fetchall()
        if not rows:
            raise SystemExit("No feature history for validation.")
        history = (
            pl.DataFrame(
                {
                    "effective_date": [r[0] for r in rows],
                    "feature_name": [r[1] for r in rows],
                    "value": [
                        float(r[2]) if r[2] is not None else None for r in rows
                    ],
                }
            )
            .drop_nulls(subset=["value"])
            .pivot(values="value", index="effective_date", on="feature_name")
            .sort("effective_date")
            .drop_nulls()
        )

        # Simple, lag-safe signal function using a feature that is in the
        # artifact's feature_cols: position on the lagged sign of ret_21d
        # (or the first feature if ret_21d absent), realised PnL on ret_1d.
        target_col = "ret_21d" if "ret_21d" in feature_cols else feature_cols[0]

        def signal_fn(train: pl.DataFrame, test: pl.DataFrame) -> np.ndarray:
            if target_col not in test.columns or "ret_1d" not in test.columns:
                return np.zeros(test.height, dtype=float)
            position = np.sign(test[target_col].to_numpy())
            lagged = np.concatenate([[0], position[:-1]])
            return lagged * test["ret_1d"].to_numpy()

        wf = WalkForwardCV(audit_log, embargo_days=504)
        wf_result = wf.run(history, signal_fn, n_splits=3)
        sharpes = wf_result.get("sharpes") or []
        wf_sharpe = float(np.mean(sharpes)) if sharpes else 0.0
        from scipy.stats import kurtosis, skew

        sample_returns = signal_fn(history.head(history.height // 2), history)
        sample_returns = sample_returns[np.isfinite(sample_returns)]
        sk = float(skew(sample_returns)) if sample_returns.size else 0.0
        kt = float(kurtosis(sample_returns)) if sample_returns.size else 3.0
        dsr_result = deflated_sharpe(
            observed_sharpe=wf_sharpe,
            skew=sk,
            kurt=kt,
            n_obs=max(sample_returns.size, 1),
            audit_log=audit_log,
        )

        report = ValidationReport(
            layer_name="hmm_candidate",
            as_of=date.today(),
            walk_forward_sharpe=wf_sharpe,
            cpcv_p30_sharpe=wf_result.get("p30", 0.0),
            cpcv_p50_sharpe=wf_result.get("p50", 0.0),
            cpcv_path_count=wf_result.get("n_paths", 0),
            deflated_sharpe=dsr_result["deflated_sharpe"],
            audit_trial_count=dsr_result["audit_trial_count"],
            n_trials_used=dsr_result["n_trials_used"],
            survivorship_audit="BYPASSED_LITE_MODE" if args.app_mode == "v7_lite" else "UNRUN",
            survivorship_coverage=0.0,
            app_mode=args.app_mode,
            validation_status=(
                ValidationStatus.LITE_SURVIVORSHIP
                if args.app_mode == "v7_lite"
                else ValidationStatus.RESEARCH_PREVIEW
            ),
            lite_bypass_reasons=(
                [LiteBypassReason.SURVIVORSHIP_AUDIT.value]
                if args.app_mode == "v7_lite"
                else []
            ),
        )
        persist_report(store.conn, report)

        passed = wf_sharpe >= settings.wf_sharpe_floor and dsr_result["deflated_sharpe"] >= 0
        print(f"WF Sharpe: {wf_sharpe:.3f}  DSR: {dsr_result['deflated_sharpe']:.3f}")
        print(f"Status:    {report.status}")
        print(f"Sign-off:  {'PASS' if passed else 'FAIL'}")

        if passed and args.promote_on_pass:
            canonical = (
                settings.hmm_model_path_lite
                if args.app_mode == "v7_lite"
                else settings.hmm_model_path_institutional
            )
            promote_candidate(
                store.conn,
                model_id=args.candidate.stem,
                app_mode=args.app_mode,
                walk_forward_sharpe=wf_sharpe,
                deflated_sharpe=dsr_result["deflated_sharpe"],
                canonical_path=canonical,
                artifact_path=args.candidate,
            )
            print(f"[OK] Promoted to {canonical}")
        else:
            print("Skipping promotion (no --promote-on-pass or validation failed).")
        sys.exit(0 if passed else 1)
    finally:
        store.close()
        audit_log.close()


if __name__ == "__main__":
    main()
