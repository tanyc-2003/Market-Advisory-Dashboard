"""Cached, deterministic LLM interface (Ollama-backed by default).

The interface is **strictly read-only**.  The system prompt below
enumerates the prohibited actions; the dashboard never bypasses it.
A 1-day TTL prevents stale interpretations from accumulating, and the
cache key includes ``as_of_date`` so re-asking the same question the
next day re-fetches a fresh inference.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

import duckdb
import structlog

from config.settings import settings
from src.advisory.data_infra.schema import bootstrap_schema

from .context import LLMContextPacket

logger = structlog.get_logger(__name__)


CACHE_TTL_DAYS: int = 1


SYSTEM_PROMPT: str = """
You are a market analyst assistant with read-only access to statistical model outputs.

You are permitted to:
- Summarise statistical outputs in plain language
- Explain what distributions and analog clusters mean
- Describe which alerts are most relevant to the query
- Generate plain-language reports from diagnostic data

You are strictly prohibited from:
- Inferring causality for market moves
- Generating trading rules or heuristics
- Assigning confidence levels not in the provided data
- Synthesising lessons or wisdom from outcome patterns
- Recommending position sizes, stop-losses, or targets
- Promoting any signal to validated status
- Overriding or explaining away contradictions

If asked to do any prohibited action, respond:
"I cannot [action] — this falls outside the permitted scope of statistical summarisation."
""".strip()


def _format_asset_list(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "(no assets surfaced)"
    return "\n".join(
        f"- {r.get('ticker', '?')}: top features "
        f"{', '.join(map(str, r.get('top_features', [])))} "
        f"(vintage {r.get('background_vintage', '?')})"
        for r in rows
    )


def _format_alerts(alerts: list[dict[str, Any]]) -> str:
    if not alerts:
        return "(no active alerts)"
    return "\n".join(
        f"- [{a.get('alert_type', '?')}] {a.get('message', a.get('label', ''))}"
        for a in alerts
    )


def build_prompt(context: LLMContextPacket) -> str:
    return (
        f"SYSTEM CONTEXT — AS OF {context.date}\n\n"
        f"MARKET STATE:\n{context.market_state}\n\n"
        f"TOP ASSETS (by model attribution):\n"
        f"{_format_asset_list(context.top_decile)}\n\n"
        f"ACTIVE ALERTS:\n{_format_alerts(context.alerts)}\n\n"
        f"CALIBRATION NOTE:\n{context.calibration_note}\n\n"
        "SYSTEM DOES NOT KNOW:\n"
        + ("\n".join(f"- {u}" for u in context.unknowns) or "(none)")
        + "\n\n"
        f"ANALYST QUERY:\n{context.analyst_query}\n"
    )


def compute_prompt_hash(model_id: str, as_of_date: date, prompt: str) -> str:
    key = f"{model_id}::{as_of_date.isoformat()}::{prompt}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _default_invoker(base_url: str, model: str) -> Callable[[str], str]:
    """Return a function that calls Ollama with temperature 0.

    Imported lazily so the rest of the module is importable without
    langchain-ollama installed.
    """

    def _call(prompt: str) -> str:
        from langchain_ollama import OllamaLLM

        llm = OllamaLLM(base_url=base_url, model=model, temperature=0)
        return str(llm.invoke(prompt))

    return _call


class CachedLLMInterface:
    """SHA-256 keyed cache around a deterministic LLM call.

    Parameters
    ----------
    db_path:
        Path to the main DuckDB.  Defaults to ``settings.main_db_path``.
    invoker:
        Optional callable ``(prompt: str) -> str`` for testing; when
        not provided, an Ollama-backed callable is built on demand.
    now:
        Optional clock for deterministic tests.
    """

    def __init__(
        self,
        db_path: Path | str | None = None,
        invoker: Callable[[str], str] | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        path = str(db_path or settings.main_db_path)
        self.conn = duckdb.connect(path)
        bootstrap_schema(self.conn)
        self._invoker_factory: Callable[[str], str] | None = invoker
        self._now = now or datetime.utcnow
        self.model_id = settings.llm_model

    def _invoke(self, prompt: str) -> str:
        if self._invoker_factory is not None:
            return self._invoker_factory(prompt)
        callable_ = _default_invoker(settings.ollama_base_url, settings.llm_model)
        return callable_(prompt)

    def _get_cached(self, prompt_hash: str) -> str | None:
        row = self.conn.execute(
            "SELECT response, created_at FROM llm_cache WHERE prompt_hash = ?",
            (prompt_hash,),
        ).fetchone()
        if row is None:
            return None
        response, created_at = row
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        if self._now() - created_at > timedelta(days=CACHE_TTL_DAYS):
            self.conn.execute(
                "DELETE FROM llm_cache WHERE prompt_hash = ?",
                (prompt_hash,),
            )
            logger.info("llm_cache_expired", prompt_hash=prompt_hash[:12])
            return None
        return str(response)

    def _put_cache(
        self, prompt_hash: str, as_of_date: date, prompt: str, response: str
    ) -> None:
        self.conn.execute(
            """
            INSERT OR REPLACE INTO llm_cache
                (prompt_hash, model_id, as_of_date, prompt, response, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                prompt_hash,
                self.model_id,
                as_of_date.isoformat(),
                prompt,
                response,
                self._now(),
            ),
        )

    def query(
        self, context: LLMContextPacket, as_of_date: date
    ) -> dict[str, Any]:
        """Return ``{"response", "cache_hit", "error", "prompt_hash"}``."""
        prompt = SYSTEM_PROMPT + "\n\n" + build_prompt(context)
        prompt_hash = compute_prompt_hash(self.model_id, as_of_date, prompt)

        cached = self._get_cached(prompt_hash)
        if cached is not None:
            return {
                "response": cached,
                "cache_hit": True,
                "error": False,
                "prompt_hash": prompt_hash,
            }

        try:
            response = self._invoke(prompt)
        except Exception as exc:  # pragma: no cover - exercised by tests
            logger.warning("llm_unreachable", error=str(exc))
            return {
                "response": "LLM service unavailable. Check Ollama is running.",
                "cache_hit": False,
                "error": True,
                "prompt_hash": prompt_hash,
            }

        self._put_cache(prompt_hash, as_of_date, prompt, response)
        return {
            "response": response,
            "cache_hit": False,
            "error": False,
            "prompt_hash": prompt_hash,
        }

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:  # pragma: no cover - defensive
            pass

    def __enter__(self) -> "CachedLLMInterface":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
