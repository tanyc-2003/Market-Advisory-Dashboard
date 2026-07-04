"""US-equities fine-tuning of the Kronos predictor (single-process, CPU-capable).

Reads the PIT ``px_*`` OHLCV archive, builds normalised sliding windows per
ticker, and runs the repo's fine-tune step — a frozen tokenizer + next-token loss
on the predictor. Saves a Hugging-Face-style checkpoint loadable straight into
``KronosTransformerForecaster`` (point ``--hf-model`` at the local directory).

The validated-only Layer 0 gate still applies to any resulting model. Real
quality needs a broad US corpus (hundreds of tickers) + more epochs + ideally a
GPU; this loop is deliberately simple so it also runs on CPU (~2s/step on
Kronos-base for a small batch).
"""
from __future__ import annotations

import os
from typing import Any, Callable

import numpy as np
import pandas as pd

FEATURES = ["open", "high", "low", "close", "volume", "amount"]
TIME_FEATURES = ["minute", "hour", "weekday", "day", "month"]
_PX = ["px_open", "px_high", "px_low", "px_close", "px_volume"]


def _ticker_frame(conn, ticker: str):
    ph = ",".join("?" * len(_PX))
    rows = conn.execute(
        f"SELECT effective_date, feature_name, feature_value FROM features_pit "
        f"WHERE ticker = ? AND feature_name IN ({ph}) ORDER BY effective_date",
        [ticker, *_PX],
    ).fetchall()
    by: dict = {}
    for d, fn, v in rows:
        if v is not None:
            by.setdefault(d, {})[fn] = float(v)
    recs = []
    for d in sorted(by):
        r = by[d]
        if all(k in r for k in _PX):
            recs.append((d, r["px_open"], r["px_high"], r["px_low"], r["px_close"], r["px_volume"]))
    if len(recs) < 120:
        return None
    df = pd.DataFrame(recs, columns=["date", "open", "high", "low", "close", "volume"])
    df["amount"] = df["volume"] * df["close"]
    ts = pd.to_datetime(df["date"])
    df["minute"] = ts.dt.minute
    df["hour"] = ts.dt.hour
    df["weekday"] = ts.dt.weekday
    df["day"] = ts.dt.day
    df["month"] = ts.dt.month
    return df


def build_windows(conn, tickers, lookback: int = 90, predict: int = 10, stride: int = 5, clip: float = 5.0):
    """Normalised sliding windows: list of (x [W,6] float32, stamp [W,5] float32).

    Windows never cross ticker boundaries; each is z-scored per-window and clipped
    exactly as the reference dataset and inference path do.
    """
    w = lookback + predict + 1
    out: list[tuple[np.ndarray, np.ndarray]] = []
    for tk in tickers:
        df = _ticker_frame(conn, tk)
        if df is None:
            continue
        feats = df[FEATURES].to_numpy(dtype=np.float32)
        stamps = df[TIME_FEATURES].to_numpy(dtype=np.float32)
        for s in range(0, len(df) - w + 1, max(1, stride)):
            x = feats[s:s + w].copy()
            mu = x.mean(axis=0)
            sd = x.std(axis=0)
            x = np.clip((x - mu) / (sd + 1e-5), -clip, clip)
            out.append((x.astype(np.float32), stamps[s:s + w].copy()))
    return out


def finetune(
    windows,
    *,
    base_model: str = "NeoQuasar/Kronos-base",
    tokenizer: str = "NeoQuasar/Kronos-Tokenizer-base",
    epochs: int = 1,
    lr: float = 2e-5,
    batch_size: int = 8,
    device: str = "cpu",
    max_steps: int | None = None,
    save_dir: str | None = None,
    log: Callable[[str], None] = print,
) -> dict[str, Any]:
    """Fine-tune the Kronos predictor on the given windows; optionally save it."""
    import torch
    from torch.utils.data import DataLoader, TensorDataset

    from .kronos_vendor import Kronos, KronosTokenizer

    if not windows:
        raise SystemExit("No training windows — is the px_* OHLCV archive populated?")

    tok = KronosTokenizer.from_pretrained(tokenizer).to(device)
    tok.eval()
    model = Kronos.from_pretrained(base_model).to(device)
    model.train()

    xs = torch.from_numpy(np.stack([w[0] for w in windows]))
    ss = torch.from_numpy(np.stack([w[1] for w in windows]))
    loader = DataLoader(TensorDataset(xs, ss), batch_size=batch_size, shuffle=True)
    opt = torch.optim.AdamW(model.parameters(), lr=lr)

    step = 0
    total = 0.0
    for _epoch in range(epochs):
        for bx, bs in loader:
            bx, bs = bx.to(device), bs.to(device)
            with torch.no_grad():
                t0, t1 = tok.encode(bx, half=True)
            logits = model(t0[:, :-1], t1[:, :-1], bs[:, :-1, :])
            loss, _s1, _s2 = model.head.compute_loss(logits[0], logits[1], t0[:, 1:], t1[:, 1:])
            opt.zero_grad()
            loss.backward()
            opt.step()
            step += 1
            total += float(loss.item())
            if step % 20 == 0 or (max_steps and step <= 5):
                log(f"  step {step}  loss {loss.item():.4f}")
            if max_steps and step >= max_steps:
                break
        if max_steps and step >= max_steps:
            break

    if save_dir:
        os.makedirs(save_dir, exist_ok=True)
        model.save_pretrained(save_dir)
        log(f"Saved fine-tuned checkpoint to {save_dir}")
    return {"steps": step, "avg_loss": total / max(step, 1), "n_windows": len(windows)}
