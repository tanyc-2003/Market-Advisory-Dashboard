#!/usr/bin/env python3
"""Fine-tune Kronos on US equities from the PIT px_* OHLCV archive.

Produces a local checkpoint you then register as a Kronos backend:

    # 1) fine-tune (single-process; runs on CPU, faster on GPU)
    python scripts/finetune_kronos.py --epochs 1 --out models/kronos_ft_us

    # 2) register the fine-tuned checkpoint as a transformer candidate + validate
    python scripts/train_kronos.py --backend transformer --hf-model models/kronos_ft_us
    python scripts/validate_kronos_candidate.py --candidate models/kronos_v7_lite_<date>.pkl --promote-on-pass
    python scripts/kronos_forecast.py

Quality note: a genuinely better model needs a broad US corpus (ingest hundreds
of tickers into px_* first) + more epochs, ideally on a GPU. The default
watchlist is a smoke-scale corpus. The result is still validated-only/gated.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import duckdb  # noqa: E402

from config.settings import settings  # noqa: E402
from src.advisory.api import analogs_live  # noqa: E402
from src.advisory.data_infra.schema import bootstrap_schema  # noqa: E402
from src.advisory.layer_kronos.finetune import build_windows, finetune  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Fine-tune Kronos on US-equity OHLCV (px_* archive)")
    ap.add_argument("--tickers", nargs="+", default=None,
                    help="Tickers to train on (default: single-name watchlist; --all-px for every px_ ticker)")
    ap.add_argument("--all-px", action="store_true", help="Use every ticker that has px_* data")
    ap.add_argument("--lookback", type=int, default=90)
    ap.add_argument("--predict", type=int, default=10)
    ap.add_argument("--stride", type=int, default=5)
    ap.add_argument("--epochs", type=int, default=1)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--max-steps", type=int, default=None, help="Cap total steps (smoke runs)")
    ap.add_argument("--base-model", default="NeoQuasar/Kronos-base")
    ap.add_argument("--tokenizer", default="NeoQuasar/Kronos-Tokenizer-base")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--out", type=Path, default=Path("models") / f"kronos_ft_us_{date.today():%Y%m%d}")
    args = ap.parse_args()

    conn = duckdb.connect(str(settings.main_db_path))
    bootstrap_schema(conn)

    if args.all_px:
        tickers = [r[0] for r in conn.execute(
            "SELECT DISTINCT ticker FROM features_pit WHERE feature_name = 'px_close' ORDER BY ticker"
        ).fetchall()]
    else:
        tickers = args.tickers or [t for t, _ in analogs_live._WATCHLIST]
    print(f"Building windows for {len(tickers)} ticker(s): {tickers}")

    windows = build_windows(conn, tickers, lookback=args.lookback, predict=args.predict, stride=args.stride)
    print(f"Built {len(windows)} training windows (lookback={args.lookback}, predict={args.predict}).")
    conn.close()

    result = finetune(
        windows, base_model=args.base_model, tokenizer=args.tokenizer,
        epochs=args.epochs, lr=args.lr, batch_size=args.batch_size,
        device=args.device, max_steps=args.max_steps, save_dir=str(args.out),
    )
    print(f"[OK] Fine-tune done: {result['steps']} steps, avg loss {result['avg_loss']:.4f}, "
          f"{result['n_windows']} windows.")
    print(f"     Checkpoint: {args.out}")
    print(f"     Register:  python scripts/train_kronos.py --backend transformer --hf-model {args.out}")


if __name__ == "__main__":
    main()
