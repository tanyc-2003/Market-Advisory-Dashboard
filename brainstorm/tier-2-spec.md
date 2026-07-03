# Tier 2 — implementation specs

Transparency & governance features. Two synthesise existing live data (no new
model); two add small append-only stores. Same conventions as
[tier-1-spec.md](tier-1-spec.md) (DDL in `schema.py`, `*_live.py` compute +
`live.py` wiring + camelCase payload + typed frontend slice + temp-DB/HTTP tests).

---

## 4. Bull / bear case synthesis

**Outcome.** For the selected ticker, a **case-for / case-against** panel built by
composing signals the dashboard already computes, shown side by side with a
plain-language verdict + confidence — reasons, not a black-box score.

### Data model
**None.** Pure synthesis of the already-assembled `assets`, `marketState`,
`calibration` blocks.

### Backend — `synthesis_live.py::build_cases(assets, market_state, calibration)`
Called in `build_dashboard()` **after** those sections are assembled (it consumes
their outputs, not the DB). For each watchlist asset, evaluate deterministic rules:

| Bull point when… | Bear point when… |
|---|---|
| driver has ↑ | driver has ↓ |
| `hitRate > 0.5` | `disagreement == true` |
| right-skew (`p50 > 0` and `p95 > \|p5\|`) | wide/left-skew (`\|p5\| > p95`) |
| dominant regime is bullish (from `marketState`) | `effectiveN < 15` |
| `sizing.displayed > 0` | recent calibration for that confidence band is overconfident |

- `verdict` = sign/magnitude of (bull − bear) → `"lean long" | "neutral" | "lean short"`.
- `confidence` = evidence strength from `effectiveN`, `disagreement`, and available
  calibration (never a probability of being right — a *confidence in the read*).
- Attach `case: { bull: string[], bear: string[], verdict, confidence }` to each
  asset item (keeps the payload cohesive; frontend already iterates `assets`).

### API payload (addition to each `assets[]` item)
```jsonc
{ "...": "existing asset fields",
  "case": { "bull": ["ret_63d ↑", "hit rate 62%", "regime: Volatile Bull"],
            "bear": ["global vs within-regime overlap 28%"],
            "verdict": "lean long", "confidence": "moderate" } }
```

### Frontend
Two-column panel (`Case for` / `Case against`) for the selected ticker, rendered
near the sizing panel in Overview, with a verdict pill (green/amber/red palette)
and the confidence. New `components/CasePanel.tsx`. No new nav item.

### Gate: **disclosed** — inherits the research-preview status of its inputs.
### Effort: **M.** Optional later: narrate the two columns with the LLM layer
(`LLM_ENABLED`) using the tiered-fallback pattern (see Tier 3 cross-cutting).

---

## 5. Decision change-log with rationale ("trading-as-git")

**Outcome.** An auditable trail of *why a recommendation moved* — when a verdict or
sizing changes materially, record a hashed diff (+ optional rationale), guarded,
appended immutably → a "what changed and why" panel.

### Data model — new table
```sql
CREATE TABLE IF NOT EXISTS recommendation_changes (
    change_id    VARCHAR PRIMARY KEY,     -- sha1(ticker|changed_at|prev_hash)
    ticker       VARCHAR   NOT NULL,
    changed_at   TIMESTAMP NOT NULL DEFAULT now(),
    field        VARCHAR   NOT NULL,      -- 'verdict' | 'sizing_band' | 'disagreement'
    prev_value   VARCHAR,
    new_value    VARCHAR,
    prev_hash    VARCHAR,                 -- content hash of the prior per-ticker state
    new_hash     VARCHAR   NOT NULL,
    rationale    VARCHAR,                 -- optional operator note (the "commit message")
    guard_passed BOOLEAN   NOT NULL DEFAULT TRUE
);
```

### Backend — `recommendation_log.py`
On each snapshot, build a compact per-ticker state `{verdict, sizing_band,
disagreement}` (sizing bucketed to, e.g., 0.05 bands so noise doesn't churn the
log) and hash it. Compare to the latest recorded `new_hash` for that ticker:
- If materially different, run **guard checks** (`sizing ≤ KELLY_ABSOLUTE_CAP`,
  valid band, verdict in enum). On pass, append a `recommendation_changes` row per
  changed field, chaining `prev_hash → new_hash` (git-like).
- `recommendation_changes_live.compute(conn)` reads the most recent N changes for
  the payload. Reuse the append-only discipline in
  `layer0_validation/audit_log.py`.

**Rationale** — `POST /api/recommendations/{ticker}/rationale` attaches an operator
note to that ticker's latest change (the commit message), returns refreshed
dashboard. Mirrors the journal POST pattern in `app.py`.

### API payload
```jsonc
"recommendationChanges": {
  "items": [ { "ticker": "MSFT", "changedAt": "2026-06-29T…", "field": "verdict",
               "prev": "neutral", "new": "lean short",
               "rationale": "regime disagreement spiked", "hash": "a1b2…" } ],
  "source": "live"
}
```

### Frontend
A timeline/history panel ("What changed") — each entry shows ticker, field,
prev→new, timestamp, and rationale (with an inline "add rationale" input like the
journal-close editor). Place under Validation or a new small view.

### Gate: audit trail, no model gate.  ### Effort: **M.**

---

## 6. Persistent per-ticker notes "inbox"

**Outcome.** Replace the ephemeral representative **alerts** panel with a
persistent, per-ticker-tagged feed that accumulates system alerts, resolved-call
outcomes, and the trader's own notes — a lightweight research memory.

### Data model — new table
```sql
CREATE TABLE IF NOT EXISTS notes (
    note_id    VARCHAR PRIMARY KEY,       -- uuid
    ticker     VARCHAR,                   -- NULL = global note
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    kind       VARCHAR NOT NULL,          -- 'alert' | 'system' | 'user' | 'outcome'
    source     VARCHAR,                   -- 'layer7' | 'freshness' | 'track_record' | 'trader'
    body       TEXT    NOT NULL,
    read       BOOLEAN NOT NULL DEFAULT FALSE
);
```

### Backend — `notes_live.py`
- **Producers** write notes: Layer 7 contradictions/calendar events, the freshness
  monitor (Tier 1 #2) on stale feeds, and the track record (Tier 1 #1) on each
  resolved prediction (`kind='outcome'`). Producers dedupe by a natural key so a
  standing condition doesn't spam.
- **Reader** `compute_notes(conn)`: recent notes, optionally filtered; unread count.
- **Endpoints:** `POST /api/notes` (add a user note: ticker?, body),
  `POST /api/notes/{id}/read`. Return refreshed dashboard.

### API payload
```jsonc
"notes": {
  "unread": 3,
  "items": [ { "id": "…", "ticker": "NVDA", "createdAt": "…", "kind": "outcome",
               "source": "track_record", "body": "Resolved +2.1% vs SPY +0.4%",
               "read": false } ],
  "source": "live"
}
```

### Frontend
A filterable feed panel (filter by ticker / unread), an add-note input, and
mark-read affordance. It supersedes the current `AlertsAndUnknowns` alerts column
(keep "unknowns" as-is). Ties the journal, track record and watchlist together.

### Gate: none (a store + feed).  ### Effort: **S–M.**

---

## Tier-2 definition of done
- [ ] `synthesis_live` producing per-ticker `case`; `CasePanel` renders for the
      selected ticker; verdict/confidence disclosed.
- [ ] `recommendation_changes` table + material-delta detection + guards + hashed
      chain + rationale POST; history panel; temp-DB + HTTP tests.
- [ ] `notes` table + producers + reader + add/read endpoints; feed panel replaces
      ephemeral alerts; unread badge.
- [ ] Every new section carries a `source` flag and degrades to representative /
      empty-state with no DB.
