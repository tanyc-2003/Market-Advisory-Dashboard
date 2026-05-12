#!/usr/bin/env python3
"""Train an HMM artifact for the V7_lite (or V7 institutional) market state engine.

Trains on whatever feature rows are present in ``features_pit``.  Writes
a dated pickle (e.g., ``models/hmm_v7_lite_20260512.pkl``), records a
candidate row in ``hmm_model_registry``, and prints the OOS-K table.

Promotion to the canonical path (``models/hmm_v7_lite.pkl``) is a
separate step — run :mod:`scripts.validate_hmm_candidate` to perform
the Layer 0 sign-off + promotion.

Usage::

    python scripts/train_hmm.py --mode v7_lite --training-end 2026-01-01
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
from src.advisory.layer1_market_state.engine import (  # noqa: E402
    train_market_state_engine,
    winsorize,
)
from src.advisory.layer1_market_state.k_selector import select_k_oos  # noqa: E402
from src.advisory.layer1_market_state.registry import register_candidate  # noqa: E402


LITE_FEATURE_COLS: list[str] = [
    "ret_1d",
    "ret_5d",
    "ret_21d",
    "realized_vol_21d",
    "pct_above_ma50",
]


def _load_market_history(store: FeatureStore, features: list[str]) -> pl.DataFrame:
    cols = ", ".join(f"'{c}'" for c in features)
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
        raise SystemExit(
            "No feature rows found. Run scripts/seed_synthetic_data.py "
            "or scripts/ingest_real_data.py first."
        )
    df = pl.DataFrame(
        {
            "effective_date": [r[0] for r in rows],
            "feature_name": [r[1] for r in rows],
            "value": [float(r[2]) if r[2] is not None else None for r in rows],
        }
    )
    return (
        df.drop_nulls(subset=["value"])
        .pivot(values="value", index="effective_date", on="feature_name")
        .sort("effective_date")
        .drop_nulls()
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Train an HMM artifact")
    parser.add_argument("--mode", default=settings.app_mode, choices=("v7_lite", "v7_institutional"))
    parser.add_argument("--training-end", type=lambda s: date.fromisoformat(s), default=date.today())
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--candidate-ks", nargs="+", type=int, default=[2, 3, 4])
    args = parser.parse_args()

    output = args.output or Path("models") / (
        f"hmm_{args.mode}_{args.training_end.strftime('%Y%m%d')}.pkl"
    )
    output.parent.mkdir(parents=True, exist_ok=True)

    store = FeatureStore(settings.main_db_path, settings.cache_dir)
    audit_log = AuditLog(settings.audit_db_path)

    try:
        history = _load_market_history(store, LITE_FEATURE_COLS)
        history = history.filter(pl.col("effective_date") <= args.training_end)
        if history.height < 200:
            raise SystemExit(
                f"Only {history.height} rows of feature history; need >= 200."
            )

        feature_cols = [c for c in LITE_FEATURE_COLS if c in history.columns]
        print(f"Training on {history.height} rows, features: {feature_cols}")

        sel = select_k_oos(
            history,
            feature_cols=feature_cols,
            candidate_ks=args.candidate_ks,
            audit_log=audit_log,
        )
        best_k = sel["selected_k"]
        print(f"Selected K = {best_k}  (OOS log-likelihoods: {sel['scores']})")

        X = history.select(feature_cols).to_numpy()
        mu = np.nanmean(X, axis=0, keepdims=True)
        sd = np.nanstd(X, axis=0, ddof=1, keepdims=True)
        engine = train_market_state_engine(
            history,
            feature_cols=feature_cols,
            k=best_k,
            audit_log=audit_log,
        )

        artifact = {
            "model": engine.hmm_model,
            "feature_cols": feature_cols,
            "sigma_cap": engine.sigma_cap,
            "training_mean": mu,
            "training_std": sd,
            "training_end_date": args.training_end,
            "k_selected": best_k,
            "oos_log_likelihood": sel["scores"][best_k],
            "n_dimensions": len(feature_cols),
            "app_mode": args.mode,
        }
        with open(output, "wb") as f:
            pickle.dump(artifact, f, protocol=5)

        model_id = output.stem
        register_candidate(
            store.conn,
            model_id=model_id,
            app_mode=args.mode,
            artifact_path=output,
            training_window_start=history["effective_date"].min(),
            training_window_end=args.training_end,
            n_dimensions=len(feature_cols),
            k_selected=best_k,
            oos_log_likelihood=sel["scores"][best_k],
        )

        print(f"[OK] Trained candidate {model_id}")
        print(f"     Artifact: {output}")
        print(f"     Registered in hmm_model_registry with status='candidate'")
        print(f"     Next: python scripts/validate_hmm_candidate.py --candidate {output} --promote-on-pass")
    finally:
        store.close()
        audit_log.close()


if __name__ == "__main__":
    main()
