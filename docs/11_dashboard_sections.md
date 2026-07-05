# 11 — Dashboard enhancement sections (Tiers 1–3)

Beyond the core layer views, the dashboard payload carries nine **enhancement
sections** drawn from a reference-repo survey and mapped onto this system's
evidence-gated, point-in-time philosophy. The planning rationale (selection
criteria, source repos, licensing, sequencing) lives in
[brainstorm/feature-roadmap.md](../brainstorm/feature-roadmap.md) and the per-tier
specs in [brainstorm/tier-1-spec.md](../brainstorm/tier-1-spec.md) …
`tier-3-spec.md`. This file is the **as-built reference**: what each section is,
its backend module, its payload key, and — critically — *how it is allowed to
appear* (its gate).

All nine are wired into `live.build_dashboard()` and follow the house
`compute_<section>(conn) -> payload | None` seam ([10_web_stack.md](10_web_stack.md)):
real when the stores/artifacts exist, otherwise a disclosed representative
fallback. Every section carries a `source` flag; model-bearing sections also
carry `validated`.

## The gate spectrum

The system has one rule — *no output is evidence until Layer 0 signs it off* — but
sections relate to it differently. Each is tagged with how it may surface:

- **validated-only** — hidden until a promoted, Layer-0-passed artifact exists.
- **disclosed** — shown with an explicit research-preview / heuristic disclosure;
  never claims `validated:true` without a real study.
- **audit / store / meta** — not a predictive model, so no Layer 0 gate; it
  *records* or *governs* rather than *forecasts*.

---

## Tier 1 — self-knowledge

### #1 System self-grading track record — `track_record_live.py` → `trackRecord`
The flagship. The system logs each watchlist call *as stated* (per ticker, per
as-of date) into `system_predictions`, then resolves it against the realised
forward return once the horizon elapses. `ret_fwd_10d` at date T *is* the realised
10-day forward return (only knowable at T+10), so resolution is PIT-honest.
Reports rolling hit rate, mean predicted vs realised, alpha vs SPY, and a
predicted-vs-realised reliability curve. **Gate:** disclosed (small sample),
strengthens over time — enough resolved calls can eventually feed a real
`ValidationReport`. Emission is explicit (`scripts/track_record.py`), never on the
GET path.

### #2 Data freshness & PIT health monitor — `data_health_live.py` → `dataHealth`
Grades the *inputs* the way Layer 0 grades outputs: per feed (equities, ^VIX, each
FRED series) the last `effective_date`, trading-days-behind, and PIT lag, from
`features_pit` + `yfinance_fetch_audit` (no new tables). Feeds classify
fresh / stale / missing (`_FRESH_MAX=2`, `_STALE_MAX=5` trading days). **Gate:**
meta — no model, but it *governs* the other sections' trustworthiness.

### #3 Forecast fan + probability tiles — `analogs_live.py`
Two model-agnostic reads on the watchlist: a per-ticker fan (median forward path +
p5–p95 band *through time*, not just a single 10-day bar) and compact tiles
`P(up in 10d)` (the analog hit rate) and `P(vol-regime shift)`. Surfaced on the
asset row from the analog engine's own output. **Gate:** disclosed, same as the
analog watchlist. (The *heavy* transformer version of the fan is #9, attached
separately at `assets[].kronos`.)

---

## Tier 2 — transparency & governance

### #4 Bull / bear case synthesis — `synthesis_live.py` → `assets[].case`
Composes signals the dashboard already computes (drivers, hit rate, distribution
skew, regime alignment, disagreement, thin-sample flags) into a side-by-side
case-for / case-against with a plain-language verdict + confidence. No new model —
it mutates each asset dict in place, adding `case`. **Gate:** disclosed; inherits
the research-preview status of its inputs.

### #5 Decision change-log "trading-as-git" — `recommendation_log.py` → `recommendationChanges`
Records *material* changes to a ticker's recommendation (verdict flip, sizing band
crossing, disagreement toggle) as an append-only, content-hashed chain, with an
optional operator rationale (the "commit message", via
`POST /api/recommendations/{ticker}/rationale`). Snapshotting is explicit
(`scripts/snapshot_recommendations.py`), never on the GET path. **Gate:** audit
trail — no gate; guard checks (Kelly cap, band validity) run before a change is
accepted.

### #6 Persistent per-ticker notes inbox — `notes_live.py` → `notes`
A durable, per-ticker-tagged feed that supersedes the ephemeral representative
alerts: system alerts (Layer 7 contradictions, calendar events, freshness
warnings), resolved-prediction outcomes (#1), and the trader's own notes
(`POST /api/notes`, `POST /api/notes/{id}/read`). Kinds: `alert`, `system`,
`user`, `outcome`. **Gate:** none — a store + feed.

---

## Tier 3 — additive inputs (gated / optional)

### #7 Composite market-stress gauge — `stress_live.py` → `stress`
A single 0–100 stress read rolled up from *real* market-wide signals in
`features_pit` (VIX percentile, HY-OAS momentum, cross-sectional realised vol,
curve inversion) with a **fixed, disclosed** weight vector. It is presentation,
not a model — it always ships `validated:false` and shows its weights. Takes
Layer 5 partly live. **Gate:** disclosed heuristic; never `validated:true` without
a real Layer-0 study. Do **not** dress it as a model.

### #8 arXiv research radar — `research_radar_live.py` → `researchRadar`
Auto-pulls recent arXiv papers matching the methods this system uses (regime/HMM,
analogs, deflated Sharpe, calibration, Kelly). The network fetch is explicit
(`scripts/research_radar.py` / a scheduler) into the `research_cache` table; the
GET path only reads the cache and never blocks on the network. **Gate:** none.

### #9 Kronos forecaster — `kronos_forecast_live.py` → `assets[].kronos`
Kronos as an **additional**, gated forward-return forecaster feeding the watchlist
fan, with uncertainty bands. Two backends share one output contract: a fast
block-bootstrap (computed on the GET path) and the heavy pretrained transformer
(precomputed out-of-band by `scripts/kronos_forecast.py` into
`kronos_forecast_cache`; the GET path just reads it). Transformer candlesticks are
reconstructed from the PIT `px_*` archive; an optional yfinance **live-edge** bar
(the current, not-yet-ingested day) may be appended for inference only — tagged
`liveEdge`, never written back into `features_pit`. **Gate:** validated-only, no
exceptions — hidden until it passes Layer 0 on *our* data (walk-forward + deflated
Sharpe). The paper's numbers don't count. See
[kronos_finetune.md](kronos_finetune.md) and [04_layers.md](04_layers.md#layer-kronos--probabilistic-forecaster)
for the model, fine-tune pipeline, and the empirical finding that Kronos-base does
*not* clear the gate.

---

## Backing tables

New tables added for these sections (DDL in
[data_infra/schema.py](../src/advisory/data_infra/schema.py), created by
`bootstrap_schema`):

| Table | Section |
|---|---|
| `system_predictions` | #1 track record (one row per ticker × as-of; resolved against `ret_fwd_10d`) |
| `recommendation_changes` | #5 decision change-log (append-only, hashed) |
| `notes` | #6 per-ticker notes inbox |
| `research_cache` | #8 arXiv radar |
| `kronos_forecast_cache` | #9 Kronos transformer forecasts (out-of-band) |
| `watchlist` | the user-editable ticker set the watchlist (#3/#4/#9 live on) — see below |

#2 (data health) and #3/#4 (fan/tiles, synthesis) add **no** tables — they reuse
`features_pit` / `yfinance_fetch_audit` and compose already-computed sections.

The watchlist those per-ticker sections render on is itself **user-editable**: a
ticker added in-app is ingested asynchronously (`watchlist` table + the
`POST`/`DELETE /api/watchlist/{ticker}` routes). Full flow in
[10_web_stack.md#dynamic-watchlist](10_web_stack.md#dynamic-watchlist).

## Cross-references
- Payload contract & the live-vs-representative seam: [10_web_stack.md](10_web_stack.md)
- The dynamic watchlist (add/remove + async ingest): [10_web_stack.md#dynamic-watchlist](10_web_stack.md#dynamic-watchlist)
- The Layer 0 invariant every gate serves: [01_overview.md](01_overview.md), [03_invariants.md](03_invariants.md)
- Kronos model + fine-tune + gate result: [kronos_finetune.md](kronos_finetune.md)
- Planning rationale and source repos: [brainstorm/feature-roadmap.md](../brainstorm/feature-roadmap.md)
