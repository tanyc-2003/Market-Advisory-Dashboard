#!/usr/bin/env python3
"""Train a Kronos forecaster candidate.

Fits + calibrates the block-bootstrap forecaster and writes a dated artifact +
a `candidate` row in the model registry. Promotion is a separate Layer-0 step:

    python scripts/train_kronos.py --mode v7_lite
    python scripts/validate_kronos_candidate.py --candidate models/kronos_v7_lite_<date>.pkl --promote-on-pass
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import duckdb  # noqa: E402
import numpy as np  # noqa: E402

from config.settings import settings  # noqa: E402
from src.advisory.data_infra.schema import bootstrap_schema  # noqa: E402
from src.advisory.layer_kronos.forecaster import train_kronos  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Train a Kronos forecaster candidate")
    ap.add_argument("--mode", default="v7_lite", choices=("v7_lite", "v7_institutional"))
    ap.add_argument("--backend", default="block_bootstrap", choices=("block_bootstrap", "transformer"),
                    help="Model backend to register as the candidate")
    ap.add_argument("--training-end", type=lambda s: date.fromisoformat(s), default=date.today())
    ap.add_argument("--calib-ticker", default="SPY", help="Return series used for the calibration forecast")
    ap.add_argument("--samples", type=int, default=16, help="transformer: stochastic samples per forecast")
    ap.add_argument("--hf-model", default="NeoQuasar/Kronos-base")
    ap.add_argument("--hf-tokenizer", default="NeoQuasar/Kronos-Tokenizer-base")
    ap.add_argument("--output", type=Path, default=None)
    args = ap.parse_args()

    conn = duckdb.connect(str(settings.main_db_path))
    bootstrap_schema(conn)

    output = args.output or Path("models") / f"kronos_{args.mode}_{args.training_end:%Y%m%d}.pkl"

    if args.backend == "transformer":
        from src.advisory.layer_kronos.transformer import KronosTransformerForecaster

        forecaster = KronosTransformerForecaster(
            hf_model=args.hf_model, hf_tokenizer=args.hf_tokenizer,
            samples=args.samples, training_end=args.training_end, app_mode=args.mode,
        )
        forecaster.save(output)
        model_id = output.stem
        conn.execute(
            "INSERT OR REPLACE INTO hmm_model_registry "
            "(model_id, app_mode, trained_at, training_window_end, validation_status, artifact_path) "
            "VALUES (?, ?, now(), ?, ?, ?)",
            [model_id, args.mode, args.training_end, "candidate", str(output)],
        )
        print(f"[OK] Registered Kronos transformer candidate {model_id} "
              f"({args.hf_model}, samples={args.samples})")
        print(f"     Artifact (config marker): {output}")
        print(f"     Next: python scripts/validate_kronos_candidate.py --candidate {output} --promote-on-pass")
        print("     Then: python scripts/kronos_forecast.py   (populate the forecast cache)")
        conn.close()
        return

    rows = conn.execute(
        "SELECT feature_value FROM features_pit WHERE ticker = ? AND feature_name = 'ret_1d' "
        "AND effective_date <= ? ORDER BY effective_date",
        [args.calib_ticker, args.training_end],
    ).fetchall()
    returns = np.array([float(r[0]) for r in rows if r[0] is not None], dtype=float)
    if returns.size < 200:
        raise SystemExit(f"Only {returns.size} returns for {args.calib_ticker}; need >= 200. Run ingest_real_data.py.")

    # Calibrate band width against the SAME series' realised forward returns, so
    # `calib` corrects only the block-bootstrap's dispersion bias (≈1) rather than
    # a cross-ticker vol mismatch. Per-ticker inference then self-scales to each
    # name's own volatility.
    frows = conn.execute(
        "SELECT feature_value FROM features_pit WHERE feature_name = 'ret_fwd_10d' "
        "AND ticker = ? AND effective_date <= ?",
        [args.calib_ticker, args.training_end],
    ).fetchall()
    realized = np.array([float(r[0]) for r in frows if r[0] is not None], dtype=float)

    forecaster = train_kronos(returns, realized, args.training_end)

    output = args.output or Path("models") / f"kronos_{args.mode}_{args.training_end:%Y%m%d}.pkl"
    forecaster.save(output)
    model_id = output.stem
    conn.execute(
        "INSERT OR REPLACE INTO hmm_model_registry "
        "(model_id, app_mode, trained_at, training_window_end, validation_status, artifact_path) "
        "VALUES (?, ?, now(), ?, ?, ?)",
        [model_id, args.mode, args.training_end, "candidate", str(output)],
    )
    print(f"[OK] Trained Kronos candidate {model_id} (calib={forecaster.calib:.2f})")
    print(f"     Artifact: {output}")
    print(f"     Next: python scripts/validate_kronos_candidate.py --candidate {output} --promote-on-pass")
    conn.close()


if __name__ == "__main__":
    main()
