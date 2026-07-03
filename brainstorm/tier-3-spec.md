# Tier 3 — implementation specs

Additive inputs, gated or optional. #7 takes Layer 5 partly live behind a
**disclosed heuristic**; #8 is peripheral; #9 is a new predictive model held to
**validated-only**. Same conventions as [tier-1-spec.md](tier-1-spec.md).

---

## 7. Composite market-stress gauge (takes Layer 5 partly live)

**Outcome.** A single 0–100 market-stress tile rolled up from *real* friction /
macro signals, with the weighting shown and a "heuristic, not validated"
disclosure. Presentation, not a model.

### Data model
Prefer no new tables. Requires these signals in `features_pit`:
- present: `vix_percentile_63d`, and the FRED macro (`hy_spread_roc_21d`).
- **may need adding** to `compute_ohlcv_features`: Amihud illiquidity z
  (`amihud_z`, from `|ret| / dollar_volume`) and a Corwin–Schultz spread proxy
  (`cs_spread_execution_proxy`). Per the V7_lite invariants these two are distinct
  (`amihud_z` → stress; CS spread → execution) and must not be substituted. Adding
  them is a one-off `features.py` change + re-ingest.

### Backend — `stress_live.py::compute_stress(conn)`
- Pull the latest cross-sectional value of each component; normalise each to 0–100
  (percentile-rank over a trailing window is the most defensible transform).
- Composite = transparent weighted sum with a fixed, **displayed** weight vector
  (e.g. VIX 0.35, HY-OAS roc 0.30, Amihud 0.20, CS-spread 0.15).
- Return `composite`, a `level` band (`calm/normal/elevated/stressed`), the
  `components` with their raw + normalised values, and the `weighting` string.
- Return `None` if the required components are absent (→ representative fallback).

### API payload
```jsonc
"stress": {
  "composite": 42, "level": "elevated",
  "components": [ { "name": "VIX %ile", "value": 0.58, "weight": 0.35 },
                  { "name": "HY OAS Δ",  "value": 0.41, "weight": 0.30 } ],
  "weighting": "heuristic (fixed weights, not a validated model)",
  "validated": false, "source": "live"
}
```

### Frontend
A semicircular **gauge** SVG tile (0–100, needle + band colour) in the Overview
header strip or a stress row; expand to show components + weights. Always render
the `weighting` disclosure inline.

### Gate: **disclosed heuristic**. Never `validated: true` without a real Layer-0
study of the composite's predictive value. If such a study is ever run, it slots
into the existing `ValidationReport` machinery.
### Effort: **M** (S if Amihud/CS already ingested).

---

## 8. Research radar (arXiv)

**Outcome.** A small side panel auto-pulling recent arXiv papers matching the
methods this system uses (regime/HMM, historical analogs, deflated Sharpe,
calibration, Kelly) with a short summary feed.

### Data model — small cache table
```sql
CREATE TABLE IF NOT EXISTS research_cache (
    entry_id    VARCHAR PRIMARY KEY,      -- arXiv id
    topic       VARCHAR NOT NULL,         -- which tracked query matched
    title       VARCHAR NOT NULL,
    authors     VARCHAR,
    published   DATE,
    url         VARCHAR,
    summary     TEXT,
    fetched_at  TIMESTAMP NOT NULL DEFAULT now()
);
```

### Backend — `research_radar_live.py`
- A cached fetcher against the arXiv Atom API for a small set of tracked queries;
  refresh at most daily (skip if `max(fetched_at)` < 24h old). Upsert into
  `research_cache`. The quant-mind arXiv connector (MIT) can be adapted directly.
- `compute_research_radar(conn)` returns the most recent N entries grouped by
  topic; degrade to whatever is cached (or empty) if arXiv is unreachable — never
  fail the dashboard.

### API payload
```jsonc
"researchRadar": {
  "fetchedAt": "2026-06-29T…",
  "items": [ { "topic": "regime detection", "title": "…", "authors": "…",
               "published": "2026-06-20", "url": "https://arxiv.org/abs/…",
               "summary": "…" } ],
  "source": "live"
}
```

### Frontend: a collapsible feed panel (secondary placement — sidebar or a
"Research" expander). Purely informational.
### Gate: none. Network-dependent; must degrade gracefully.
### Effort: **S.** Lowest-risk item here; peripheral to the core loop.

---

## 9. Kronos forecaster as a gated ensemble input

**Outcome.** A probabilistic OHLCV forecaster (Kronos, Apache-2.0) feeding the
watchlist as a *second, independent* forward-return view with uncertainty bands —
**only after it passes Layer 0 on our data.**

### Data model — registry (mirror the HMM registry)
Reuse `hmm_model_registry` conventions or add `kronos_model_registry`
(`model_id, trained_at, training_window, validation_status, walk_forward_sharpe,
deflated_sharpe, artifact_path, retired_at`). Artifacts are git-ignored
(`models/*.pkl`/weights), like the HMM.

### Backend — `kronos_forecast_live.py`
- Load the **promoted** artifact only (mirror `market_state_live._load_engine`'s
  canonical-vs-candidate logic). Produce per-ticker forecast bands → feed the fan
  chart (Tier 1 #3) as a second series, or a separate `kronosForecast` block.
- **Validation is mandatory and identical to the HMM path:** walk-forward CV +
  CPCV + deflated Sharpe on *our* features via `validate_hmm_candidate`-style
  script; the paper's numbers do not count. A `train_kronos.py` +
  `validate_kronos_candidate.py` pair mirrors the existing HMM scripts.

### API payload — present **only when validated**
```jsonc
"assets[].kronos": { "p5": -0.06, "p50": 0.01, "p95": 0.08, "validated": true }
```

### Frontend
When present, overlay a second band/line on the fan chart (labelled "Kronos") so
the two forecasts are visually comparable. Hidden entirely when not validated.

### Gate: **validated-only** — stricter than every other feature. Unlike the
disclosed-preview modules, an unvalidated Kronos is **hidden**, not shown, because
it is a new predictive claim. Lowest priority: Tier 1 #3 already delivers the fan
*visualisation* without this model's validation + dependency weight (torch, etc.).
### Effort: **L.**

---

## Cross-cutting (land alongside the panels that need them)

### Data-access contract hardening (TradingAgents v0.3.0)
The API already degrades *with disclosure* (every section has a `source` flag),
honouring the spirit. Add the missing half:
- **Strict mode** (`STRICT_FRESHNESS`, defined in Tier 1 #2): a stale/missing
  critical feed refuses rather than serves.
- **Deterministic entity resolution:** a single ticker-normalisation helper in the
  data layer (upper-case, alias map, reject unknowns) used by ingestion + the
  journal POST, so the same name always resolves the same way.

### Tiered LLM fallback (World Monitor)
Only once narrative panels exist (bull/bear case #4, transition notes). Wrap
`layer_llm/CachedLLMInterface` in a fallback chain (local Ollama → provider →
lightweight) so summaries degrade gracefully. Stays behind `LLM_ENABLED`; never on
the critical data path.

---

## Tier-3 definition of done
- [ ] `stress_live` composite gauge with displayed weights + heuristic disclosure;
      Amihud/CS added to features if needed; temp-DB + HTTP tests.
- [ ] `research_radar_live` + `research_cache` + collapsible feed; graceful offline.
- [ ] Kronos path **only** merges behind a passing Layer-0 report; hidden until then.
- [ ] Strict-freshness + entity-resolution helpers wired; LLM fallback chain when
      narrative panels ship.
