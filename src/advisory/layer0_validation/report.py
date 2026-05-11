"""ValidationReport + `requires_production` decorator.

A :class:`ValidationReport` is the single authoritative artifact that
records whether a layer's outputs are evidentiary (``production``),
research-grade only (``research_preview``), or unsafe to display
(``blocked``).

The :func:`requires_production` decorator wraps any layer method that
must not run unless its report carries ``production_ready=True``.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from functools import wraps
from typing import Any, Callable, Literal, Optional


class ValidationGateError(RuntimeError):
    """Raised when a layer method runs without production sign-off."""


Status = Literal["production", "research_preview", "blocked"]


@dataclass
class ValidationReport:
    """Bundle of validation evidence for a single layer.

    All thresholds are read from :mod:`config.settings`; this dataclass
    only carries the observed metrics and derived sign-off state.
    """

    layer_name: str
    as_of: date

    # Walk-forward / out-of-sample evidence
    walk_forward_sharpe: float = 0.0
    walk_forward_ece: float = 1.0  # default is a *failing* ECE

    # CPCV evidence
    cpcv_p30_sharpe: float = 0.0
    cpcv_p50_sharpe: float = 0.0
    cpcv_path_count: int = 0

    # Deflated Sharpe
    deflated_sharpe: float = 0.0
    audit_trial_count: int = 0
    n_trials_used: int = 0

    # Survivorship
    survivorship_audit: Literal["PASSED", "FAILED", "UNRUN"] = "UNRUN"
    survivorship_coverage: float = 0.0

    # Optional extras (used by Layers 1 / 2 reports)
    hmm_k_selected: Optional[int] = None
    cpcv_fallback: Optional[str] = None
    dimensionality_r2: Optional[float] = None

    # Result fields populated by :func:`validate_layer`
    production_ready: bool = False
    rationale: str = ""
    extras: dict[str, Any] = field(default_factory=dict)

    @property
    def status(self) -> Status:
        if (
            self.survivorship_audit == "FAILED"
            or self.walk_forward_sharpe <= 0
        ):
            return "blocked"
        if self.production_ready:
            return "production"
        return "research_preview"

    def to_dashboard_dict(self) -> dict[str, Any]:
        """JSON-safe flat dict for serialisation / templating."""
        d = asdict(self)
        d["as_of"] = self.as_of.isoformat()
        d["status"] = self.status
        return d


def validate_layer(report: ValidationReport) -> str:
    """Apply the five sign-off criteria and mutate the report in place.

    Returns one of ``"production"``, ``"research_preview"``, ``"blocked"``.

    Criteria (architecture §5):
      1. Survivorship audit PASSED
      2. Walk-forward Sharpe >= floor
      3. Walk-forward ECE <= ceiling
      4. CPCV 30th-percentile Sharpe >= floor
      5. Deflated Sharpe >= floor
    """
    # Import inside to avoid a circular import at module load.
    from config.settings import settings

    reasons: list[str] = []

    if report.survivorship_audit == "FAILED":
        reasons.append("survivorship audit FAILED")
    elif report.survivorship_audit != "PASSED":
        reasons.append("survivorship audit not run")

    if report.walk_forward_sharpe < settings.wf_sharpe_floor:
        reasons.append(
            f"walk_forward_sharpe={report.walk_forward_sharpe:.3f} "
            f"< floor {settings.wf_sharpe_floor:.2f}"
        )

    if report.walk_forward_ece > settings.wf_ece_ceiling:
        reasons.append(
            f"walk_forward_ece={report.walk_forward_ece:.3f} "
            f"> ceiling {settings.wf_ece_ceiling:.2f}"
        )

    if report.cpcv_p30_sharpe < settings.cpcv_p30_floor:
        reasons.append(
            f"cpcv_p30_sharpe={report.cpcv_p30_sharpe:.3f} "
            f"< floor {settings.cpcv_p30_floor:.2f}"
        )

    if report.deflated_sharpe < settings.dsr_floor:
        reasons.append(
            f"deflated_sharpe={report.deflated_sharpe:.3f} "
            f"< floor {settings.dsr_floor:.2f}"
        )

    if not reasons:
        report.production_ready = True
        report.rationale = "all sign-off criteria met"
    else:
        report.production_ready = False
        report.rationale = "; ".join(reasons)

    return report.status


def requires_production(get_report: Callable[[], ValidationReport]) -> Callable:
    """Decorator factory: gate a method on its layer's ValidationReport.

    Usage::

        class Layer:
            def __init__(self, report):
                self.report = report
                self.method = requires_production(lambda: self.report)(self._method)
    """

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            report = get_report()
            if not report.production_ready:
                raise ValidationGateError(
                    f"Layer '{report.layer_name}' is not production_ready. "
                    f"Status: {report.status}. Rationale: {report.rationale}"
                )
            return fn(*args, **kwargs)

        return wrapper

    return decorator
