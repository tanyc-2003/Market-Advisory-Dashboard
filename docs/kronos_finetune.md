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
#    broader corpus on a GPU (after ingesting more tickers into px_*):
python scripts/finetune_kronos.py --all-px --epochs 10 --batch-size 32 \
    --device cuda --save-every 100 --out models/kronos_ft_us_gpu
#    (CUDA torch: pip install torch --index-url https://download.pytorch.org/whl/cu126)
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

- **Speed:** ~2 s/training step on Kronos-base on CPU (batch 2). On an RTX 4050
  (6 GB) with `--device cuda --batch-size 32` it's ~0.4 s/step warm and peaks at
  ~4.6 GB VRAM, so a full 10-epoch pass over the 84-ticker corpus (~12.7k steps)
  is ~20 min — a real fine-tune, versus hours on CPU.
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
- **Empirical (CPU, light pass).** A short run — 84 US tickers ingested (~1.05M
  `px_*` rows), ~10k windows, 300 steps (~24% of one epoch) at lr 2e-5 — did
  **not** meaningfully shift the raw forecasts: NVDA marginally less bearish
  (−8.1% → −5.3% 10d), GOOGL slightly worse, AAPL flat, `pUp` still ≈ 0. The loss
  barely moved (~3.4 → ~3.0, noisy). 300 steps is far too little to re-adapt a
  100M-param model.
- **Empirical (GPU, real pass).** The full run on an RTX 4050 (`torch 2.9.1+cu126`,
  `--device cuda --batch-size 32`) — 40,572 windows, **10 epochs / 12,680 steps**,
  ~20 min — trained properly: loss fell **3.4 → ~2.2** on a clean descent. It
  **fixed the transfer pathology**: the base model is uniformly bearish (`pUp ≈ 0`
  on nearly everything, a Chinese-A-share/crypto artifact); the fine-tuned model
  *discriminates* — AAPL/SPY near-neutral (`pUp` 0.31 / 0.50), momentum names
  bullish. But it **over-corrects into bull-drift overfitting**: NVDA +19%, MSFT
  +35% (10d) are implausible — training next-token over the 2016–2026 mega-cap
  uptrend, the model memorises drift. Takeaway: a real GPU fine-tune solves the
  transfer problem but needs (a) drift-neutralising calibration and/or (b)
  training on de-trended returns, then (c) the Layer 0 walk-forward gate to decide
  if the calibrated signal is actually evidence. The raw shift is real; promotion
  still has to be earned.
- **Adjudication (does it earn promotion?) — no.** Two independent checks on the
  GPU fine-tune both say *keep it gated*:
  - *Calibration* neutralised the bull drift with a per-ticker negative bias, but
    MSFT hit the ±10% cap (`bias=-0.10`) — the model's drift exceeds what
    calibration can remove.
  - *Shipped Layer 0 gate* (trailing-drift proxy): **FAIL** — WF Sharpe 0.135
    (below floor), deflated Sharpe 0.0 against the 2000-trial audit floor.
  - *Model-specific directional backtest* (the rigorous test — 10 tickers, 170
    ticker-dates, 10d horizon): the fine-tune **did not add skill**. The
    information coefficient (corr of forecast vs realised fwd return) *fell*
    +0.271 → +0.190, and that comparison is stacked in the fine-tune's favour
    (base is out-of-sample, fine-tuned is in-sample). Its higher hit-rate (0.58 vs
    0.51) is beta — it goes long 57% of the time in a market that averaged
    +2.3%/10d. Sign-following either model (~1.0%) **loses to buy-and-hold**
    (+2.3%). No tradable directional edge.

  Conclusion: the GPU fine-tune produces a real, visible re-centring of the
  forecasts but **no evidence-grade skill**, so it stays hidden behind Layer 0 —
  the system working as designed. A clean time-split OOS fine-tuned IC would only
  be lower than the in-sample 0.190, so it would harden, not overturn, this.

## What was verified in-repo

The pipeline is smoke-verified on CPU: `build_windows` over the PIT archive, a few
real training steps (loss decreasing loop), `save_pretrained` → `from_pretrained`
round-trip, and a forecast produced from the fine-tuned checkpoint through
`KronosTransformerForecaster`. A full-quality fine-tune (broad corpus, many
epochs, GPU) is left to run out-of-band.
