"""Block-bootstrap Monte-Carlo probabilistic forecaster (Kronos backend)."""
from __future__ import annotations

import pickle
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

DEFAULT_HORIZONS: tuple[int, ...] = (1, 3, 5, 10)


@dataclass
class KronosForecaster:
    """Probabilistic forward-return forecaster via stationary block bootstrap.

    Simulating cumulative-return paths by resampling contiguous blocks of the
    ticker's own daily returns preserves volatility clustering and autocorrelation
    — giving a genuine uncertainty fan rather than an i.i.d. band.
    """

    block_size: int = 5
    n_sims: int = 500
    horizons: tuple[int, ...] = DEFAULT_HORIZONS
    calib: float = 1.0                 # band-width multiplier, fit in train_kronos
    lookback: int = 504               # trailing days of returns used per forecast
    seed: int = 42
    training_end: date | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    # ---- inference ----

    def point_forecast(self, returns: np.ndarray) -> float:
        """Cheap median cumulative-return estimate (drift) over the max horizon —
        used as the directional signal in validation."""
        r = np.asarray(returns, dtype=float)
        r = r[np.isfinite(r)]
        if r.size == 0:
            return 0.0
        recent = r[-min(r.size, self.lookback):]
        return float(np.mean(recent) * max(self.horizons))

    def _simulate(self, returns: np.ndarray) -> np.ndarray:
        r = np.asarray(returns, dtype=float)
        r = r[np.isfinite(r)]
        r = r[-min(r.size, self.lookback):]
        if r.size < self.block_size + 5:
            raise ValueError("insufficient return history")
        rng = np.random.default_rng(self.seed)
        h_max = max(self.horizons)
        max_start = r.size - self.block_size
        dret = np.empty((self.n_sims, h_max))
        for i in range(self.n_sims):
            seq: list[float] = []
            while len(seq) < h_max:
                s = int(rng.integers(0, max_start + 1))
                seq.extend(r[s:s + self.block_size].tolist())
            dret[i] = seq[:h_max]
        return dret

    def forecast(self, returns: np.ndarray, current_vol_annual: float | None = None) -> dict[str, Any] | None:
        try:
            dret = self._simulate(returns)
        except ValueError:
            return None
        paths = np.cumprod(1.0 + dret, axis=1) - 1.0  # cumulative simple return per step

        bands: list[dict[str, float]] = []
        for h in self.horizons:
            col = paths[:, h - 1]
            med = float(np.median(col))
            p5 = med + (float(np.percentile(col, 5)) - med) * self.calib
            p95 = med + (float(np.percentile(col, 95)) - med) * self.calib
            bands.append({"h": int(h), "p5": p5, "p50": med, "p95": p95})

        terminal = paths[:, max(self.horizons) - 1]
        p_up = float((terminal > 0).mean())

        p_vol_shift: float | None = None
        if current_vol_annual is not None and current_vol_annual > 0:
            sim_vol_annual = dret.std(axis=1) * np.sqrt(252.0)
            p_vol_shift = float((sim_vol_annual > current_vol_annual).mean())

        return {
            "forecast": bands,
            "p50": bands[-1]["p50"], "p5": bands[-1]["p5"], "p95": bands[-1]["p95"],
            "pUp": p_up, "pVolShift": p_vol_shift,
        }

    # ---- persistence ----

    def to_artifact(self, app_mode: str = "v7_lite") -> dict[str, Any]:
        return {
            "kind": "kronos_block_bootstrap",
            "block_size": self.block_size, "n_sims": self.n_sims,
            "horizons": list(self.horizons), "calib": self.calib,
            "lookback": self.lookback, "seed": self.seed,
            "training_end": self.training_end, "app_mode": app_mode,
            "extras": self.extras,
        }

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as fh:
            pickle.dump(self.to_artifact(), fh, protocol=5)

    @classmethod
    def load(cls, path: Path) -> "KronosForecaster":
        with open(path, "rb") as fh:
            art = pickle.load(fh)
        return cls(
            block_size=int(art.get("block_size", 5)),
            n_sims=int(art.get("n_sims", 500)),
            horizons=tuple(art.get("horizons", DEFAULT_HORIZONS)),
            calib=float(art.get("calib", 1.0)),
            lookback=int(art.get("lookback", 504)),
            seed=int(art.get("seed", 42)),
            training_end=art.get("training_end"),
            extras=art.get("extras", {}),
        )


def load_forecaster(path: Path):
    """Load whichever backend the artifact declares (block-bootstrap or transformer)."""
    with open(path, "rb") as fh:
        art = pickle.load(fh)
    if art.get("kind") == "kronos_transformer":
        from .transformer import KronosTransformerForecaster

        return KronosTransformerForecaster.from_artifact(art)
    return KronosForecaster.load(path)


def train_kronos(
    returns: np.ndarray,
    realized_fwd_10d: np.ndarray,
    training_end: date,
) -> KronosForecaster:
    """Fit the forecaster and calibrate its band width so the 10-day p5–p95 range
    matches the empirical spread of realised forward returns in the training data."""
    f = KronosForecaster(training_end=training_end)
    fc = f.forecast(returns)
    emp = np.asarray(realized_fwd_10d, dtype=float)
    emp = emp[np.isfinite(emp)]
    if fc is not None and emp.size > 30:
        model_width = fc["forecast"][-1]["p95"] - fc["forecast"][-1]["p5"]
        emp_width = float(np.percentile(emp, 95) - np.percentile(emp, 5))
        if model_width > 0 and emp_width > 0:
            f.calib = float(np.clip(emp_width / model_width, 0.5, 3.0))
    f.extras["n_train_returns"] = int(np.isfinite(returns).sum())
    return f
