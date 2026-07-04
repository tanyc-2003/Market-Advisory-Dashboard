# Fine-tuning Kronos on US equities

The pretrained Kronos-base transfers poorly to US mega-caps (it's trained largely
on Chinese A-shares / crypto), so its raw forecasts skew bearish and calibration
can only paper over that. The real fix is to **fine-tune the predictor on US
equity candlesticks**. This repo ships a CPU-capable, single-process fine-tune
path that reuses the PIT `px_*` OHLCV archive and plugs the result straight into
the existing validated-only Kronos wiring.

Requires the `[kronos]` extra: `pip install -e ".[kronos]"`.

## Pipeline

```
features_pit (px_open/high/low/close/volume)         # PIT OHLCV archive
        │  build_windows()  → normalised sliding windows (lookback+predict+1)
        ▼
scripts/finetune_kronos.py                            # frozen tokenizer + next-token loss on the predictor
        │  model.save_pretrained(models/kronos_ft_us_<date>/)   # HF-style checkpoint
        ▼
scripts/train_kronos.py --backend transformer --hf-model models/kronos_ft_us_<date>
        │  (config-marker artifact points at the local checkpoint)
        ▼
scripts/validate_kronos_candidate.py … --promote-on-pass   # Layer 0 gate — unchanged
        ▼
scripts/kronos_forecast.py                            # refresh the forecast cache
```

`KronosTransformerForecaster` loads `hf_model` via `from_pretrained`, which
accepts a **local directory** — so a fine-tuned checkpoint is a drop-in for the
HF-hub id, no code change.

## Commands

```bash
# 0) make sure the px_* archive exists (persisted by ingest_real_data.py)
python scripts/ingest_real_data.py

# 1) fine-tune (defaults: single-name watchlist, lookback 90, 1 epoch)
python scripts/finetune_kronos.py --epochs 1 --out models/kronos_ft_us
#    broader corpus (after ingesting more tickers into px_*):
python scripts/finetune_kronos.py --all-px --epochs 3 --batch-size 16 --out models/kronos_ft_us
#    quick smoke:
python scripts/finetune_kronos.py --tickers NVDA MSFT --max-steps 3 --batch-size 2 --out /tmp/kft

# 2) register the fine-tuned checkpoint as a transformer candidate
python scripts/train_kronos.py --backend transformer --hf-model models/kronos_ft_us

# 3) gate + activate (only displays if it passes Layer 0)
python scripts/validate_kronos_candidate.py --candidate models/kronos_v7_lite_<date>.pkl --promote-on-pass
python scripts/kronos_forecast.py
```

Key `finetune_kronos.py` flags: `--tickers` / `--all-px`, `--lookback`,
`--predict`, `--stride`, `--epochs`, `--lr`, `--batch-size`, `--max-steps`,
`--save-every` (intermediate checkpoints), `--base-model` (resume from a prior
checkpoint), `--device` (`cuda` if available), `--out`.

## Cost & quality notes

- **Speed:** ~2 s/training step on Kronos-base on CPU (batch 2); a modest run of a
  few hundred steps is ~15 min on CPU, far faster on a GPU (`--device cuda`).
- **Corpus:** the default watchlist (5 names) is *smoke-scale*. A genuinely better
  model needs a broad US universe — ingest hundreds of tickers into `px_*` first
  (`ingest_real_data.py --tickers …`) and train with `--all-px`.
- **Windows never cross ticker boundaries**; each is z-scored per-window and
  clipped exactly as inference does, so training and serving see the same
  distribution.
- **Still gated.** A fine-tuned model is *validated-only* like any other Kronos
  backend: it stays hidden until it clears the Layer 0 walk-forward + deflated
  Sharpe gate. Fine-tuning improves the *forecast*; the gate still decides whether
  it's evidence.
- **Empirical (CPU, light pass).** A real run — 84 US tickers ingested (~1.05M
  `px_*` rows), 10,164 windows, 300 steps (~24% of one epoch) at lr 2e-5 — did
  **not** meaningfully shift the raw forecasts: NVDA marginally less bearish
  (−8.1% → −5.3% 10d), GOOGL slightly worse (−26.8% → −33.5%), AAPL flat, `pUp`
  still ≈ 0. The loss barely moved (~3.4 → ~3.0, noisy). Meaningful US-adaptation
  needs **many epochs over the broad corpus on a GPU**; the pipeline supports
  resuming (`--base-model models/kronos_ft_us`) to accumulate steps toward that.

## What was verified in-repo

The pipeline is smoke-verified on CPU: `build_windows` over the PIT archive, a few
real training steps (loss decreasing loop), `save_pretrained` → `from_pretrained`
round-trip, and a forecast produced from the fine-tuned checkpoint through
`KronosTransformerForecaster`. A full-quality fine-tune (broad corpus, many
epochs, GPU) is left to run out-of-band.
