"""Layer 0 — validation substrate that gates every other layer."""
from .audit_log import AuditLog
from .continuous_validator import ContinuousValidator
from .cpcv import CPCVRunner
from .deflated_sharpe import STATIC_TRIAL_FLOOR, deflated_sharpe
from .report import (
    LiteBypassReason,
    ValidationGateError,
    ValidationReport,
    ValidationStatus,
    load_latest_report,
    persist_report,
    requires_production,
    validate_layer,
)
from .survivorship import SurvivorshipAuditError, SurvivorshipAuditor
from .walk_forward import WalkForwardCV

__all__ = [
    "AuditLog",
    "ContinuousValidator",
    "CPCVRunner",
    "LiteBypassReason",
    "STATIC_TRIAL_FLOOR",
    "SurvivorshipAuditError",
    "SurvivorshipAuditor",
    "ValidationGateError",
    "ValidationReport",
    "ValidationStatus",
    "WalkForwardCV",
    "deflated_sharpe",
    "load_latest_report",
    "persist_report",
    "requires_production",
    "validate_layer",
]
