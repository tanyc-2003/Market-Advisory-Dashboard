"""Residual-factor PCA anomaly detector.

Runs ``BOOTSTRAP_N`` bootstrap PCAs on the residual matrix from Layer 4's
fundamental block; clusters of co-loading tickers that appear in ≥ 80%
of bootstraps (Jaccard ≥ 0.70) are kept as alerts.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import structlog

logger = structlog.get_logger(__name__)


BOOTSTRAP_N: int = 100
JACCARD_MATCH_THRESHOLD: float = 0.70
STABILITY_THRESHOLD: float = 0.80
LOADING_CUTOFF: float = 0.30
MIN_CLUSTER_TICKERS: int = 3


class ResidualFactorAnomalyDetector:
    """Bootstrap-stable hidden-factor detector on residuals.

    Parameters
    ----------
    n_components:
        Number of leading principal components to inspect.
    bootstrap_n:
        Number of resamples — defaults to :data:`BOOTSTRAP_N`.
    seed:
        Random seed; consumed via ``np.random.default_rng`` so global
        state is not mutated.
    """

    def __init__(
        self,
        n_components: int = 3,
        bootstrap_n: int = BOOTSTRAP_N,
        seed: int = 42,
    ) -> None:
        self.n_components = n_components
        self.bootstrap_n = bootstrap_n
        self.seed = seed

    @staticmethod
    def _pca_clusters(
        residuals: pd.DataFrame, n_components: int
    ) -> list[set[str]]:
        X = residuals.fillna(0.0).to_numpy()
        if X.shape[0] < 2 or X.shape[1] < MIN_CLUSTER_TICKERS:
            return []
        X = X - X.mean(axis=0, keepdims=True)
        try:
            _, _, vt = np.linalg.svd(X, full_matrices=False)
        except np.linalg.LinAlgError:
            return []
        clusters: list[set[str]] = []
        tickers = list(residuals.columns)
        for k in range(min(n_components, vt.shape[0])):
            loadings = vt[k]
            mask = np.abs(loadings) >= LOADING_CUTOFF
            members = {tickers[i] for i, m in enumerate(mask) if m}
            if len(members) >= MIN_CLUSTER_TICKERS:
                clusters.append(members)
        return clusters

    @staticmethod
    def _jaccard(a: set[str], b: set[str]) -> float:
        if not a and not b:
            return 1.0
        union = len(a | b)
        return len(a & b) / union if union else 0.0

    def detect_hidden_concentration(
        self, residuals: pd.DataFrame
    ) -> dict[str, Any]:
        """Return human-readable alerts for stable hidden factor clusters."""
        n_obs, n_feat = residuals.shape
        if n_obs < 5 * n_feat:
            logger.warning(
                "residual_pca_poorly_conditioned",
                n_obs=n_obs,
                n_feat=n_feat,
            )

        rng = np.random.default_rng(self.seed)
        all_bootstrap_clusters: list[list[set[str]]] = []
        for _ in range(self.bootstrap_n):
            idx = rng.integers(0, n_obs, size=n_obs)
            sample = residuals.iloc[idx]
            all_bootstrap_clusters.append(
                self._pca_clusters(sample, self.n_components)
            )

        # For each cluster from the *baseline* fit, measure the fraction
        # of bootstraps that contain a Jaccard-matching cluster.
        baseline = self._pca_clusters(residuals, self.n_components)
        stable_alerts: list[dict[str, Any]] = []
        for cluster in baseline:
            matches = 0
            for boot_clusters in all_bootstrap_clusters:
                for bc in boot_clusters:
                    if self._jaccard(cluster, bc) >= JACCARD_MATCH_THRESHOLD:
                        matches += 1
                        break
            stability = matches / self.bootstrap_n if self.bootstrap_n else 0.0
            if stability < STABILITY_THRESHOLD:
                continue
            sorted_members = sorted(cluster)
            stable_alerts.append(
                {
                    "members": sorted_members,
                    "n_members": len(sorted_members),
                    "stability": stability,
                    "message": (
                        f"Hidden residual factor links "
                        f"{len(sorted_members)} tickers "
                        f"({', '.join(sorted_members)}). "
                        f"Stability {stability:.2f} across {self.bootstrap_n} "
                        f"bootstraps."
                    ),
                }
            )

        return {
            "alerts": stable_alerts,
            "n_alerts": len(stable_alerts),
            "bootstrap_n": self.bootstrap_n,
        }
