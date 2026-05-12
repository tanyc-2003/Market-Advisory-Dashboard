"""Optional LLM interpretation layer.

Off the critical path: ``settings.llm_enabled`` must be True before
anything in this module is invoked from the dashboard.  Even when
enabled, the LLM is strictly read-only — it cannot promote a signal
to ``production``, override contradictions, infer causality, or
recommend position sizes.  The prohibitions are enforced at the prompt
level (see :data:`SYSTEM_PROMPT`).
"""
from .context import LLMContextPacket, build_context_packet, estimate_tokens
from .interface import (
    CACHE_TTL_DAYS,
    CachedLLMInterface,
    SYSTEM_PROMPT,
    build_prompt,
    compute_prompt_hash,
)

__all__ = [
    "CACHE_TTL_DAYS",
    "CachedLLMInterface",
    "LLMContextPacket",
    "SYSTEM_PROMPT",
    "build_context_packet",
    "build_prompt",
    "compute_prompt_hash",
    "estimate_tokens",
]
