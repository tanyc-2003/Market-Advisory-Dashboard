# 08 — Optional LLM Interpretation (Phase 13)

**Off the critical path.** The system is complete and useful without this layer. Enable it only if you (a) want plain-English summaries of validated outputs, and (b) understand that the LLM is strictly read-only.

## Why it's optional

LLMs are fluent. Fluency is the failure mode this whole architecture is designed against: a confident-sounding output is dangerous when the underlying evidence is weak. The LLM layer is therefore:

- **Read-only.** The system prompt forbids inferring causality, recommending sizes, promoting signals, or overriding contradictions.
- **Deterministic.** Ollama is called at temperature 0.
- **Cached with a 1-day TTL.** Stale interpretations cannot accumulate.
- **Off by default.** `settings.llm_enabled` is `False`. Only `.env` may turn it on.

## Enabling it

```bash
# 1. Install Ollama and pull a model
ollama pull llama3

# 2. Edit .env
LLM_ENABLED=true
LLM_MODEL=llama3
OLLAMA_BASE_URL=http://localhost:11434

# 3. Restart Streamlit
streamlit run src/advisory/dashboard/app.py
```

Page 8 will now respond instead of stopping. The dashboard reads `settings.llm_enabled` once per page render and follows it.

## What the LLM is and is not allowed to do

The system prompt is in [src/advisory/layer_llm/interface.py](../src/advisory/layer_llm/interface.py) as `SYSTEM_PROMPT`. It is reproduced verbatim into every prompt and the dashboard never strips it.

**Permitted:**
- Summarise statistical outputs in plain language.
- Explain what distributions and analog clusters mean.
- Describe which alerts are most relevant to the query.
- Generate plain-language reports from diagnostic data.

**Strictly prohibited:**
- Inferring causality for market moves.
- Generating trading rules or heuristics.
- Assigning confidence levels not in the provided data.
- Synthesising lessons or wisdom from outcome patterns.
- Recommending position sizes, stop-losses, or targets.
- Promoting any signal to validated status.
- Overriding or explaining away contradictions.

If asked to do something prohibited, the LLM is instructed to refuse with `"I cannot [action] — this falls outside the permitted scope of statistical summarisation."`

## Context packet

`build_context_packet(...)` produces an `LLMContextPacket` that is bounded at ~2,000 tokens. The builder shrinks the asset list (then the alert list) until the packet fits. The market-state prose is truncated to 3 sentences.

```python
@dataclass
class LLMContextPacket:
    date: str
    market_state: str                  # <= 3 sentences
    top_decile: list[dict]             # up to 15 assets with attribution summary
    alerts: list[dict]                 # up to 5 alerts, severity-ranked
    calibration_note: str
    unknowns: list[str]
    analyst_query: str
```

Token estimation uses `len(text.split()) * 1.3` — cheap but conservative.

## Cache design

```python
prompt_hash = sha256(f"{model_id}::{as_of_date.isoformat()}::{prompt}").hexdigest()
```

- Same query on the same day → cache hit.
- Same query on a different day → different hash → forced cache miss → fresh inference.
- Entries older than `CACHE_TTL_DAYS = 1` are silently deleted on read.

The `llm_cache` table is created idempotently by `bootstrap_schema`. Schema:

```sql
CREATE TABLE IF NOT EXISTS llm_cache (
    prompt_hash   VARCHAR PRIMARY KEY,
    model_id      VARCHAR NOT NULL,
    as_of_date    DATE    NOT NULL,
    prompt        TEXT    NOT NULL,
    response      TEXT    NOT NULL,
    created_at    TIMESTAMP NOT NULL DEFAULT now()
);
```

Every `query(...)` response includes a `cache_hit` flag. The dashboard surfaces it as `Cached (TTL 1d)` or `Live inference`.

## Graceful degradation

If Ollama is unreachable, `query(...)` returns:

```python
{
    "response": "LLM service unavailable. Check Ollama is running.",
    "cache_hit": False,
    "error": True,
    "prompt_hash": "<sha256>",
}
```

It never raises. The dashboard renders the response with `st.error` and lets the rest of the page proceed.

## Prompt structure

```
SYSTEM CONTEXT — AS OF {date}

MARKET STATE:
{summary, <=3 sentences}

TOP ASSETS (by model attribution):
- TICKER: top features f1, f2, f3 (vintage YYYY-MM-DD)
- ...

ACTIVE ALERTS:
- [alert_type] message
- ...

CALIBRATION NOTE:
{1 sentence}

SYSTEM DOES NOT KNOW:
- {unknown 1}
- {unknown 2}

ANALYST QUERY:
{query}
```

The section headers and order are part of the contract — do not collapse or reorder them.

## Testing

`tests/unit/test_llm/` covers cache hit/miss, TTL expiry, hash collision properties, prohibited-action enforcement in the prompt, and graceful degradation when the invoker raises. The real Ollama call is replaced with a stub `invoker` callable.
