"""Advisory Market Intelligence Dashboard."""
from __future__ import annotations

import structlog

structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ]
)

__version__ = "0.1.0"
