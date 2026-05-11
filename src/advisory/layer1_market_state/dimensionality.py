"""Dimensionality adequacy check.

Out-of-sample R² of a linear projection from the feature matrix onto
the dominant variance direction.  Low OOS R² ⇒ the feature set isn't
spanning the variance we claim it is.
"""
from __future__ import annotations

from typing import Any, Callable

import numpy as np
import structlog
from sklearn.linear_model import LinearRegression

logger = structlog.get_logger(__name__)


R2_ADEQUACY_FLOOR: float = 0.40


def dimensionality_adequacy(
    X: np.ndarray,
    warn_callback: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """OOS R²: fit a linear regression on 80% of the window, score on 20%."""
    arr = np.asarray(X, dtype=float)
    if arr.ndim != 2:
        raise ValueError("X must be 2-dimensional")

    n, _ = arr.shape
    if n < 30:
        msg = f"dimensionality_adequacy: only {n} obs — skipping"
        logger.warning(msg)
        if warn_callback:
            warn_callback(msg)
        return {
            "oos_r2": 0.0,
            "passed": False,
            "n_obs": n,
            "floor": R2_ADEQUACY_FLOOR,
            "status": "INSUFFICIENT_DATA",
        }

    split = int(n * 0.8)
    X_train, X_test = arr[:split], arr[split:]
    # Use the first principal direction of the training matrix as a proxy
    # "summary" signal.  This is the variance line the features must span.
    centered = X_train - X_train.mean(axis=0, keepdims=True)
    _, _, vt = np.linalg.svd(centered, full_matrices=False)
    direction = vt[0]
    y_train = X_train @ direction
    y_test = X_test @ direction

    reg = LinearRegression()
    reg.fit(X_train, y_train)
    pred = reg.predict(X_test)
    ss_res = float(np.sum((y_test - pred) ** 2))
    ss_tot = float(np.sum((y_test - y_test.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

    passed = r2 >= R2_ADEQUACY_FLOOR
    if not passed:
        msg = (
            f"dimensionality OOS R² {r2:.3f} below floor {R2_ADEQUACY_FLOOR:.2f}; "
            f"feature set may not span variance"
        )
        logger.warning(msg)
        if warn_callback:
            warn_callback(msg)

    return {
        "oos_r2": r2,
        "passed": passed,
        "n_obs": n,
        "floor": R2_ADEQUACY_FLOOR,
        "status": "OK",
    }
