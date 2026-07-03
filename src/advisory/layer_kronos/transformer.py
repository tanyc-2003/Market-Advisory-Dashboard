"""Pretrained-transformer backend for Kronos (torch + HF weights).

Wraps the vendored Kronos model (shiyu-coder/Kronos, Apache-2.0) behind the same
`forecast(...) -> dict` contract the block-bootstrap backend uses, so it drops in
without touching the API/gate. Because ``KronosPredictor.predict`` returns the
*mean* path, we draw M stochastic samples and take percentiles for a genuine fan.

Heavy: each sample is a full autoregressive inference (~seconds on CPU), so this
backend is run out-of-band by ``scripts/kronos_forecast.py`` into a cache the API
reads — never on the request path.
"""
from __future__ import annotations

import pickle
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

DEFAULT_HORIZONS: tuple[int, ...] = (1, 3, 5, 10)


@dataclass
class KronosTransformerForecaster:
    hf_model: str = "NeoQuasar/Kronos-base"
    hf_tokenizer: str = "NeoQuasar/Kronos-Tokenizer-base"
    device: str = "cpu"
    max_context: int = 512
    samples: int = 16
    horizons: tuple[int, ...] = DEFAULT_HORIZONS
    top_p: float = 0.9
    temperature: float = 1.0
    calib: float = 1.0
    training_end: date | None = None
    app_mode: str = "v7_lite"
    extras: dict[str, Any] = field(default_factory=dict)
    _predictor: Any = field(default=None, init=False, repr=False)

    # ---- model loading ----

    def _ensure_predictor(self):
        if self._predictor is None:
            from .kronos_vendor import Kronos, KronosPredictor, KronosTokenizer

            tok = KronosTokenizer.from_pretrained(self.hf_tokenizer)
            mdl = Kronos.from_pretrained(self.hf_model)
            self._predictor = KronosPredictor(mdl, tok, device=self.device, max_context=self.max_context)
        return self._predictor

    # ---- inference ----

    def _sample_closes(self, ohlcv_df: pd.DataFrame, x_ts: pd.Series, y_ts: pd.Series) -> np.ndarray:
        predictor = self._ensure_predictor()
        h_max = max(self.horizons)
        closes = np.empty((self.samples, h_max))
        for i in range(self.samples):
            out = predictor.predict(
                df=ohlcv_df, x_timestamp=x_ts, y_timestamp=y_ts, pred_len=h_max,
                T=self.temperature, top_p=self.top_p, sample_count=1, verbose=False,
            )
            closes[i] = out["close"].to_numpy()[:h_max]
        return closes

    def forecast(
        self,
        ohlcv_df: pd.DataFrame,
        x_timestamp: pd.Series,
        y_timestamp: pd.Series,
        current_vol_annual: float | None = None,
    ) -> dict[str, Any] | None:
        if ohlcv_df is None or len(ohlcv_df) < 60:
            return None
        last_close = float(ohlcv_df["close"].iloc[-1])
        if not np.isfinite(last_close) or last_close <= 0:
            return None
        closes = self._sample_closes(ohlcv_df, x_timestamp, y_timestamp)
        rets = closes / last_close - 1.0  # cumulative simple return per step, per sample

        bands: list[dict[str, float]] = []
        for h in self.horizons:
            col = rets[:, h - 1]
            med = float(np.median(col))
            p5 = med + (float(np.percentile(col, 5)) - med) * self.calib
            p95 = med + (float(np.percentile(col, 95)) - med) * self.calib
            bands.append({"h": int(h), "p5": p5, "p50": med, "p95": p95})

        terminal = rets[:, -1]
        p_up = float((terminal > 0).mean())

        p_vol_shift: float | None = None
        if current_vol_annual is not None and current_vol_annual > 0:
            dlog = np.diff(np.log(np.clip(closes, 1e-9, None)), axis=1)
            sim_vol_annual = dlog.std(axis=1) * np.sqrt(252.0)
            p_vol_shift = float((sim_vol_annual > current_vol_annual).mean())

        return {
            "forecast": bands,
            "p5": bands[-1]["p5"], "p50": bands[-1]["p50"], "p95": bands[-1]["p95"],
            "pUp": p_up, "pVolShift": p_vol_shift,
        }

    def point_forecast(self, ohlcv_df: pd.DataFrame, x_timestamp: pd.Series, y_timestamp: pd.Series) -> float:
        """Median terminal cumulative return — the directional signal for validation."""
        fc = self.forecast(ohlcv_df, x_timestamp, y_timestamp)
        return 0.0 if fc is None else fc["p50"]

    # ---- persistence (config marker only; weights live in the HF cache) ----

    def to_artifact(self) -> dict[str, Any]:
        return {
            "kind": "kronos_transformer",
            "hf_model": self.hf_model, "hf_tokenizer": self.hf_tokenizer,
            "device": self.device, "max_context": self.max_context,
            "samples": self.samples, "horizons": list(self.horizons),
            "top_p": self.top_p, "temperature": self.temperature, "calib": self.calib,
            "training_end": self.training_end, "app_mode": self.app_mode, "extras": self.extras,
        }

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as fh:
            pickle.dump(self.to_artifact(), fh, protocol=5)

    @classmethod
    def from_artifact(cls, art: dict[str, Any]) -> "KronosTransformerForecaster":
        return cls(
            hf_model=art.get("hf_model", "NeoQuasar/Kronos-base"),
            hf_tokenizer=art.get("hf_tokenizer", "NeoQuasar/Kronos-Tokenizer-base"),
            device=art.get("device", "cpu"), max_context=int(art.get("max_context", 512)),
            samples=int(art.get("samples", 16)), horizons=tuple(art.get("horizons", DEFAULT_HORIZONS)),
            top_p=float(art.get("top_p", 0.9)), temperature=float(art.get("temperature", 1.0)),
            calib=float(art.get("calib", 1.0)), training_end=art.get("training_end"),
            app_mode=art.get("app_mode", "v7_lite"), extras=art.get("extras", {}),
        )
