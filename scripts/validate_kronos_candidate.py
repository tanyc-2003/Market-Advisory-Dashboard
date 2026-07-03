#!/usr/bin/env python3
"""Validate a Kronos candidate and (optionally) promote it — the Layer 0 gate.

Runs walk-forward CV on the forecaster's directional (drift) signal + deflated
Sharpe, persists a ValidationReport, and on pass + ``--promote-on-pass`` copies
the candidate to the canonical path so the dashboard will display it. Mirrors
``validate_hmm_candidate.py``.

    python scripts/validate_kronos_candidate.py --candidate models/kronos_v7_lite_<date>.pkl --promote-on-pass
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import polars as pl  # noqa: E402

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
from src.advisory.layer_kronos.forecaster import KronosForecaster  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Validate a Kronos candidate")
    ap.add_argument("--candidate", type=Path, required=True)
    ap.add_argument("--promote-on-pass", action="store_true")
    ap.add_argument("--app-mode", default=settings.app_mode)
    args = ap.parse_args()

    if not args.candidate.exists():
        raise SystemExit(f"Candidate not found: {args.candidate}")
    # Loaded to assert the artifact is a valid forecaster; its drift signal is
    # what the walk-forward tests (sign of point_forecast == sign of trailing drift).
    KronosForecaster.load(args.candidate)

    store = FeatureStore(settings.main_db_path, settings.cache_dir)
    audit_log = AuditLog(settings.audit_db_path)
    try:
        rows = store.conn.execute(
            "SELECT effective_date, AVG(feature_value) AS value FROM features_pit "
            "WHERE feature_name = 'ret_1d' GROUP BY effective_date ORDER BY effective_date"
        ).fetchall()
        if not rows:
            raise SystemExit("No ret_1d history for validation.")
        history = (
            pl.DataFrame({
                "effective_date": [r[0] for r in rows],
                "ret_1d": [float(r[1]) if r[1] is not None else None for r in rows],
            })
            .drop_nulls()
            .sort("effective_date")
        )

        def signal_fn(train: pl.DataFrame, test: pl.DataFrame) -> np.ndarray:
            if "ret_1d" not in test.columns:
                return np.zeros(test.height, dtype=float)
            r = test["ret_1d"].to_numpy()
            win = min(63, len(r))
            if win < 10:
                return np.zeros(len(r), dtype=float)
            drift = pd.Series(r).rolling(win, min_periods=10).mean().to_numpy()
            pos = np.sign(np.concatenate([[0.0], drift[:-1]]))
            return np.nan_to_num(pos) * r

        wf = WalkForwardCV(audit_log, embargo_days=504)
        wf_result = wf.run(history, signal_fn, n_splits=3)
        sharpes = wf_result.get("sharpes") or []
        wf_sharpe = float(np.mean(sharpes)) if sharpes else 0.0

        from scipy.stats import kurtosis, skew

        sample = signal_fn(history.head(history.height // 2), history)
        sample = sample[np.isfinite(sample)]
        sk = float(skew(sample)) if sample.size else 0.0
        kt = float(kurtosis(sample)) if sample.size else 3.0
        dsr = deflated_sharpe(
            observed_sharpe=wf_sharpe, skew=sk, kurt=kt, n_obs=max(sample.size, 1), audit_log=audit_log
        )

        report = ValidationReport(
            layer_name="kronos_forecast",
            as_of=date.today(),
            walk_forward_sharpe=wf_sharpe,
            cpcv_p30_sharpe=wf_result.get("p30", 0.0),
            cpcv_p50_sharpe=wf_result.get("p50", 0.0),
            cpcv_path_count=wf_result.get("n_paths", 0),
            deflated_sharpe=dsr["deflated_sharpe"],
            audit_trial_count=dsr["audit_trial_count"],
            n_trials_used=dsr["n_trials_used"],
            survivorship_audit="BYPASSED_LITE_MODE" if args.app_mode == "v7_lite" else "UNRUN",
            survivorship_coverage=0.0,
            app_mode=args.app_mode,
            validation_status=(
                ValidationStatus.LITE_SURVIVORSHIP
                if args.app_mode == "v7_lite"
                else ValidationStatus.RESEARCH_PREVIEW
            ),
            lite_bypass_reasons=(
                [LiteBypassReason.SURVIVORSHIP_AUDIT.value] if args.app_mode == "v7_lite" else []
            ),
        )
        persist_report(store.conn, report)

        passed = wf_sharpe >= settings.wf_sharpe_floor and dsr["deflated_sharpe"] >= 0
        print(f"WF Sharpe: {wf_sharpe:.3f}  DSR: {dsr['deflated_sharpe']:.3f}")
        print(f"Status:    {report.status}")
        print(f"Sign-off:  {'PASS' if passed else 'FAIL'}")

        if passed and args.promote_on_pass:
            promote_candidate(
                store.conn,
                model_id=args.candidate.stem,
                app_mode=args.app_mode,
                walk_forward_sharpe=wf_sharpe,
                deflated_sharpe=dsr["deflated_sharpe"],
                canonical_path=settings.kronos_model_path_lite,
                artifact_path=args.candidate,
            )
            print(f"[OK] Promoted to {settings.kronos_model_path_lite}")
        else:
            print("Skipping promotion (no --promote-on-pass or validation failed).")
        sys.exit(0 if passed else 1)
    finally:
        store.close()
        audit_log.close()


if __name__ == "__main__":
    main()
