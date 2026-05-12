"""Fundamental risk model: three regression flavours, all T-1-lagged.

The :func:`FundamentalRiskModel._aligned_lagged_inputs` method enforces
the T-1 invariant with an assertion that cannot be bypassed.  Removing
the ``.shift(1)`` would be a silent look-ahead contamination, so the
assertion is loud by design.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import structlog
from statsmodels.regression.linear_model import WLS
from statsmodels.regression.quantile_regression import QuantReg
from statsmodels.tools.tools import add_constant

from ..layer0_validation.audit_log import AuditLog
from .factors import FACTOR_ORDER

logger = structlog.get_logger(__name__)


EW_LAMBDA_SHORT: float = 0.97   # half-life ≈ 23 days (short-horizon betas)
EW_LAMBDA_MEDIUM: float = 0.99  # half-life ≈ 69 days (medium-horizon betas)
MIN_N_OBS: int = 80


# CPCV embargo (504 days) is anchored to the longest lookback below.
TAIL_BETA_LOOKBACK_DAYS: int = 504


@dataclass
class AssetExposureResult:
    """Typed wrapper around `fit_ew_ols` output for Layer 6 consumption."""

    ticker: str
    factor_exposures: dict[str, dict[str, Any]]
    r_squared: float
    idiosyncratic_pct: float
    n_obs: int
    lag_enforced: bool
    status: str  # "OK" | "SKIPPED_INSUFFICIENT_DATA"


LAYER4_LOCK_MESSAGE: str = (
    "Layer 4 (Hybrid Risk Model) is locked in V7_lite mode. "
    "Point-in-Time fundamental factor returns (Sharadar) are required. "
    "Upgrade to V7 Institutional or see the roadmap."
)


class FundamentalRiskModel:
    """Exponentially-weighted OLS + ridge + tail-beta regressions.

    Every method records to the audit log before fitting.

    In V7_lite mode (``app_mode="v7_lite"``) every public regression
    method returns ``{"status": "LOCKED"}`` — the model still
    instantiates cleanly so the dashboard can show a locked tile
    without crashing.
    """

    def __init__(
        self, audit_log: AuditLog, app_mode: str = "v7_institutional"
    ) -> None:
        self.audit_log = audit_log
        self.app_mode = app_mode
        self._locked = app_mode == "v7_lite"

    def _locked_response(self, ticker: str) -> dict[str, Any]:
        return {
            "ticker": ticker,
            "status": "LOCKED",
            "message": LAYER4_LOCK_MESSAGE,
            "factor_exposures": {},
            "lag_enforced": True,
        }

    # --- internals --------------------------------------------------------

    def _aligned_lagged_inputs(
        self,
        factor_returns: pd.DataFrame,
        asset_returns: pd.Series,
    ) -> tuple[pd.DataFrame, pd.Series]:
        """Align factor returns at T-1 with asset returns at T."""
        factor_returns = factor_returns.copy().sort_index()
        asset_returns = asset_returns.copy().sort_index()
        lagged_factors = factor_returns.shift(1)
        df = lagged_factors.join(asset_returns.rename("asset"), how="inner").dropna()
        if df.empty:
            return df.iloc[:, :-1], df.iloc[:, -1:].squeeze(axis=1)

        lagged_factors = df.iloc[:, :-1]
        aligned_asset = df.iloc[:, -1]

        # T-1 invariant: factor return labelled at row T must have come
        # from the *prior* trading day's factor return.  After the inner
        # join + dropna the indices coincide, but the *values* in
        # lagged_factors at index T must equal factor_returns at T-1.
        # Reconstruct that test directly:
        anchor = factor_returns.index.max()
        # Pick any factor and confirm its lagged value matches the prior
        # observation in the *original* factor frame.
        ref_col = lagged_factors.columns[0]
        ref_idx = lagged_factors.index
        original_prev = factor_returns[ref_col].shift(1).reindex(ref_idx)
        assert np.allclose(
            lagged_factors[ref_col].to_numpy(),
            original_prev.to_numpy(),
            equal_nan=True,
        ), (
            "T-1 lag assertion failed: lagged factor values do not match "
            "the shift(1) of the input factor returns. This is a "
            "look-ahead contamination. Halting."
        )
        # Sanity: the *latest* lagged row's index cannot exceed the
        # latest factor index (it should be <= anchor).
        assert lagged_factors.index.max() <= anchor, (
            "T-1 lag assertion failed: aligned frame extends past the "
            "input factor frame's last date."
        )
        return lagged_factors, aligned_asset

    @staticmethod
    def _ew_weights(n: int, lam: float) -> np.ndarray:
        """Most-recent observation carries the highest weight."""
        powers = np.arange(n - 1, -1, -1)
        return lam ** powers

    # --- public regressions -----------------------------------------------

    def fit_ew_ols(
        self,
        ticker: str,
        factor_returns: pd.DataFrame,
        asset_returns: pd.Series,
        lam: float = EW_LAMBDA_SHORT,
    ) -> dict[str, Any]:
        if self._locked:
            return self._locked_response(ticker)
        self.audit_log.record(
            "layer4", "fit_ew_ols", {"ticker": ticker, "lambda": lam}
        )
        X, y = self._aligned_lagged_inputs(factor_returns, asset_returns)
        n = len(y)
        if n < MIN_N_OBS:
            return self._skipped(ticker, n)

        w = self._ew_weights(n, lam)
        X_ = add_constant(X, has_constant="add")
        model = WLS(y, X_, weights=w).fit()

        factor_exposures: dict[str, dict[str, Any]] = {}
        for name in FACTOR_ORDER:
            if name not in model.params.index:
                continue
            beta = float(model.params[name])
            tstat = float(model.tvalues[name])
            factor_exposures[name] = {
                "beta": beta,
                "t_stat": tstat,
                "significant": abs(tstat) >= 1.96,
            }
        # Idiosyncratic share = residual variance / total variance
        resid_var = float(np.var(model.resid, ddof=1))
        y_var = float(np.var(y, ddof=1))
        idio = resid_var / y_var if y_var > 0 else 1.0

        return {
            "ticker": ticker,
            "method": "ew_ols",
            "factor_exposures": factor_exposures,
            "r_squared": float(model.rsquared),
            "idiosyncratic_pct": idio,
            "n_obs": int(n),
            "lag_enforced": True,
            "status": "OK",
        }

    def fit_ridge(
        self,
        ticker: str,
        factor_returns: pd.DataFrame,
        asset_returns: pd.Series,
        alpha: float = 1.0,
    ) -> dict[str, Any]:
        if self._locked:
            return self._locked_response(ticker)
        self.audit_log.record(
            "layer4", "fit_ridge", {"ticker": ticker, "alpha": alpha}
        )
        X, y = self._aligned_lagged_inputs(factor_returns, asset_returns)
        n = len(y)
        if n < MIN_N_OBS:
            return self._skipped(ticker, n)
        # Centre + scale for numerical stability of the ridge solution.
        X_arr = X.to_numpy()
        y_arr = y.to_numpy()
        X_mean = X_arr.mean(axis=0)
        X_std = X_arr.std(axis=0, ddof=1)
        X_std = np.where(X_std > 0, X_std, 1.0)
        Xs = (X_arr - X_mean) / X_std
        beta_s = np.linalg.solve(
            Xs.T @ Xs + alpha * np.eye(Xs.shape[1]),
            Xs.T @ (y_arr - y_arr.mean()),
        )
        beta = beta_s / X_std
        intercept = y_arr.mean() - beta @ X_mean
        pred = X_arr @ beta + intercept
        resid = y_arr - pred
        ss_res = float(np.sum(resid**2))
        ss_tot = float(np.sum((y_arr - y_arr.mean()) ** 2))
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

        factor_exposures = {
            name: {
                "beta": float(beta[i]),
                "t_stat": float("nan"),
                "significant": False,
            }
            for i, name in enumerate(X.columns)
        }
        return {
            "ticker": ticker,
            "method": "ridge",
            "alpha": alpha,
            "factor_exposures": factor_exposures,
            "r_squared": r2,
            "idiosyncratic_pct": (ss_res / ss_tot) if ss_tot > 0 else 1.0,
            "n_obs": int(n),
            "lag_enforced": True,
            "status": "OK",
        }

    def fit_tail_betas(
        self,
        ticker: str,
        factor_returns: pd.DataFrame,
        asset_returns: pd.Series,
        lookback_days: int = TAIL_BETA_LOOKBACK_DAYS,
    ) -> dict[str, Any]:
        if self._locked:
            return self._locked_response(ticker)
        self.audit_log.record(
            "layer4",
            "fit_tail_betas",
            {"ticker": ticker, "lookback_days": lookback_days},
        )
        # Truncate to the lookback window first to keep the runtime sane.
        if asset_returns.empty:
            return self._skipped(ticker, 0)
        anchor = asset_returns.index.max()
        cutoff = anchor - pd.Timedelta(days=lookback_days + 30)
        factor_sub = factor_returns.loc[factor_returns.index >= cutoff]
        asset_sub = asset_returns.loc[asset_returns.index >= cutoff]
        X, y = self._aligned_lagged_inputs(factor_sub, asset_sub)
        n = len(y)
        if n < MIN_N_OBS:
            return self._skipped(ticker, n)

        X_ = add_constant(X, has_constant="add")
        tails: dict[str, dict[str, float]] = {}
        for q_label, q in [("downside_5", 0.05), ("upside_95", 0.95)]:
            try:
                res = QuantReg(y, X_).fit(q=q)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning(
                    "quantreg_failed", ticker=ticker, q=q, error=str(exc)
                )
                continue
            tails[q_label] = {
                name: float(res.params[name])
                for name in FACTOR_ORDER
                if name in res.params.index
            }
        return {
            "ticker": ticker,
            "method": "tail_betas",
            "tail_betas": tails,
            "lookback_days": lookback_days,
            "n_obs": int(n),
            "lag_enforced": True,
            "status": "OK",
        }

    @staticmethod
    def _skipped(ticker: str, n_obs: int) -> dict[str, Any]:
        return {
            "ticker": ticker,
            "factor_exposures": {},
            "r_squared": 0.0,
            "idiosyncratic_pct": 1.0,
            "n_obs": int(n_obs),
            "lag_enforced": True,
            "status": "SKIPPED_INSUFFICIENT_DATA",
        }

    @staticmethod
    def to_dataclass(result: dict[str, Any]) -> AssetExposureResult:
        return AssetExposureResult(
            ticker=result["ticker"],
            factor_exposures=result.get("factor_exposures", {}),
            r_squared=float(result.get("r_squared", 0.0)),
            idiosyncratic_pct=float(result.get("idiosyncratic_pct", 1.0)),
            n_obs=int(result.get("n_obs", 0)),
            lag_enforced=bool(result.get("lag_enforced", True)),
            status=result["status"],
        )
