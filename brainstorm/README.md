# brainstorm/

Planning + specification material for candidate dashboard enhancements. **Not
committed work** — this folder is for review and prioritisation. Nothing here
ships until it's built behind the usual gates (Layer 0 sign-off / disclosed
research-preview) and verified.

| File | What it is |
|---|---|
| [feature-roadmap.md](feature-roadmap.md) | The roadmap: patterns from 5 reference repos mapped onto this dashboard, prioritised into tiers, with fit judgment, a skip list, and a licensing table. Start here. |
| [tier-1-spec.md](tier-1-spec.md) | Build-first specs: system self-grading track record, data freshness/PIT monitor, forecast fan chart + probability tiles. |
| [tier-2-spec.md](tier-2-spec.md) | Transparency & governance specs: bull/bear case synthesis, decision change-log ("trading-as-git"), persistent per-ticker notes inbox. |
| [tier-3-spec.md](tier-3-spec.md) | Gated / optional specs: composite stress gauge, arXiv research radar, Kronos forecaster (validated-only), + cross-cutting contract/LLM hardening. |

Each spec follows the codebase's existing seam so it drops in without new
infrastructure: DDL in `src/advisory/data_infra/schema.py`, a
`src/advisory/api/<section>_live.py` compute wired through `live.build_dashboard()`
with a representative fallback, a camelCase payload slice consumed by a typed
frontend view, and temp-DB + real-HTTP verification. See
[../docs/10_web_stack.md](../docs/10_web_stack.md) for that architecture.

Suggested build order (from the roadmap): **A** self-knowledge (track record +
freshness) → **B** polish/synthesis (fan chart + bull/bear) → **C** governance
(change-log + notes) → **D** gated new signals (stress → radar → Kronos).
