"""Realistic paper-trading harness.

The harness models the *adverse* side of the spread as the resting price,
square-root impact, and friction-driven excess slippage.  Midpoint fills
are impossible by construction; this is the architectural guarantee.
"""
from .harness import RealisticExecutionHarness

__all__ = ["RealisticExecutionHarness"]
