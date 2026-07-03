# Feature roadmap — enhancements drawn from reference repos

> Planning note, not a spec. Draws on TradingAgents, quant-mind, OpenAlice,
> Kronos and World Monitor as **references for patterns**, mapped onto *this*
> dashboard's architecture and philosophy. Not committed as a PR.

## How I picked (selection criteria)

Ranked against, in order:

1. **Fit with the evidence-gated / PIT philosophy.** Everything here already
   lives under "no output is evidence until Layer 0 signs it off" and "surface
   with disclosure, never degrade silently." A feature that reinforces that loop
   beats a feature that just adds a number.
2. **Reuse of what exists.** The `presentation.py` (representative source of
   truth) + `*_live.py` (live wiring) seam, the DuckDB stores (`features_pit`,
   `journal_entries`, `validation_reports`, `backtest_executions`,
   `yfinance_fetch_audit`), and the single `/api/dashboard` payload contract make
   some of these nearly free. Prefer those.
3. **Stay in the advisory-only lane.** The dashboard proposes and grades; it does
   not execute, size for real money, or move funds. Anything that assumes
   execution or a live brokerage account is out of scope.
4. **Patterns over code, mind the licence.** Kronos / quant-mind / TradingAgents
   are MIT/Apache (code reuse is fine). OpenAlice and World Monitor are AGPL-3.0
   (World Monitor additionally commercial-gated) — re-implement the *idea*, don't
   vendor the source.

The single biggest **gap** in today's dashboard drove the top pick: the system
grades the *trader* (journal → calibration) but it **never grades itself**. It
shows today's analog/regime calls and their disclaimers, then forgets them. Two
of the reference repos (TradingAgents' decision log, OpenAlice's snapshots)
point straight at that gap.

## Baseline (what already exists, so we don't rebuild it)

- **Views:** Overview (Layer-0 gate strip, market state, sizing, watchlist,
  alerts, unknowns), Portfolio, Journal (log + close), Calibration, Validation.
- **Live now:** market state (HMM regime occupancy, Layer 1), watchlist analogs +
  Kelly sizing (Layers 2/10), calibration from closed journal entries (Layer 9),
  the journal, survivorship coverage, DSR audit count.
- **Representative still:** portfolio/stress (Layer 6), alerts (Layer 7), Layer-0
  gate metrics (overlays real `ValidationReport`s when present).
- **Data spine:** bitemporal `features_pit` (PIT, `knowledge_date < T`), a
  monotonic audit log, `yfinance_fetch_audit`, the HMM registry.
- **Philosophy already enforced:** T-1 lag, Kelly cap 0.20, disclosed
  research-preview fallbacks, `source`/`validated` flags on every live section.

## Priority at a glance

| # | Feature | Source repo(s) | Fit | Effort | Gate |
|---|---|---|---|---|---|
| 1 | System self-grading track record | TradingAgents, OpenAlice | ★★★ | M | disclosed → validated |
| 2 | Data freshness & PIT health monitor | World Monitor, TradingAgents | ★★★ | S–M | n/a (meta) |
| 3 | Forecast fan chart + probability tiles | Kronos | ★★★ | S–M | disclosed |
| 4 | Bull / bear case synthesis | TradingAgents | ★★☆ | M | disclosed |
| 5 | Decision change-log w/ rationale (trading-as-git) | OpenAlice | ★★☆ | M | n/a (audit) |
| 6 | Persistent per-ticker notes "inbox" | OpenAlice | ★★☆ | S–M | n/a |
| 7 | Composite market-stress gauge (Layer 5 live) | World Monitor | ★★☆ | M | disclosed |
| 8 | Research radar (arXiv) | quant-mind | ★☆☆ | S | n/a |
| 9 | Kronos forecaster as gated ensemble input | Kronos | ★★☆ | L | validated-only |

★ = fit with this dashboard. Effort S/M/L. "Gate" = how the output is allowed to
appear (disclosed research-preview vs. must pass Layer 0).

---

## Tier 1 — build first

### 1. System self-grading track record  *(flagship)*
**From:** TradingAgents' persistent decision log; OpenAlice's account snapshots →
equity curve.

**What it is.** Every time the watchlist emits a call (per ticker: predicted
median forward return, hit probability, sizing), persist it *as stated* with its
`knowledge_date`. Ten trading days later, resolve it against the realised return
and against a benchmark (SPY), then show a panel where the **system grades its own
past calls** — rolling hit rate, mean realised vs. predicted, alpha vs. benchmark,
and a reliability curve of predicted-vs-realised. Reflection feeds back as a
disclosure ("analog calls have run +X% hit over the last N resolved predictions").

**Why it fits (my call).** This is the purest expression of the dashboard's own
thesis and the biggest missing piece. Calibration already does this for the
*trader's* confidence; this does it for the *system's* forecasts. It also turns
the existing research-preview disclaimers into something empirical — instead of
"deflated Sharpe < floor," the watchlist can eventually say "resolved hit rate
0.54 over 120 calls." That's a stronger, honest signal than a static banner.

**How to build it here.**
- New DuckDB table `system_predictions` (in `data_infra/schema.py`):
  `prediction_id, as_of/knowledge_date, ticker, horizon_days, pred_p50, pred_hit_prob,
  pred_sizing, realized_ret, benchmark_ret, alpha, resolved`.
- Emit at snapshot time from `analogs_live.py` (write the row when a watchlist is
  computed; dedupe by `(ticker, knowledge_date)`).
- A resolver (`scripts/resolve_predictions.py` + a `track_record_live.py` reader):
  resolution is essentially free — `features_pit` already stores `ret_fwd_10d` at
  each date, which *is* the realised forward return, only knowable at T+10. Join
  each unresolved prediction to `ret_fwd_10d` at its `knowledge_date` once T+10
  has passed; alpha = ticker − SPY.
- New API section `track_record_live.py` → `build_dashboard()`; new frontend view
  or a panel under Validation/Calibration (reuse the reliability-diagram
  component). Same `source`/fallback pattern as the other live modules.

**Gate.** Ships disclosed (small sample) and *strengthens over time*; once a layer
has enough resolved calls it can feed a real `ValidationReport`.

---

### 2. Data freshness & PIT health monitor
**From:** World Monitor's freshness monitor; TradingAgents' data-access contract.

**What it is.** A meta-panel that grades the *inputs* the way Layer 0 grades the
outputs: per source/feed (yfinance equities, ^VIX, each FRED series), show last
`effective_date`, staleness vs. expected cadence, missing-bar fraction, and the
PIT lag (`knowledge_date` vs `effective_date`). Stale feeds are flagged red and
their dependent panels inherit a "stale input" disclosure rather than silently
serving old numbers.

**Why it fits.** This is the PIT instinct applied to ingestion instead of
backtests — exactly the dashboard's existing discipline, one layer earlier. It's
also mostly *already in the data*: `yfinance_fetch_audit` records fetch status /
`n_bad_rows` / `n_consec_gaps`, and `features_pit` has the dates. The Streamlit UI
had a staleness banner (`is_data_stale`); this promotes it to a first-class,
per-feed health view for the React app.

**How to build it here.**
- New `data_health_live.py`: query `max(effective_date)`, row counts and gap stats
  per `(source, ticker/series)` from `features_pit` + `yfinance_fetch_audit`;
  classify each feed fresh/stale/missing against an expected cadence.
- Add a `dataHealth` block to the payload + a compact panel (sidebar expander or a
  small "Data" view). Wire the existing `meta.asOf`/staleness into it.
- Optional hard mode: a `STRICT_FRESHNESS` setting that turns a stale critical feed
  into a refusal (the "reject, don't silently serve" half of the data contract),
  consistent with the gate philosophy.

**Gate.** Meta-panel; no model, so no Layer 0 gate — but it *governs* the others.

---

### 3. Forecast fan chart + compact probability tiles
**From:** Kronos' forecast visualisation and its two demo tiles.

**What it is.** Two additions, both **model-agnostic** and driven by data we
already compute:
- A per-ticker **fan chart** on the selected watchlist name: historical price
  line, median forward path, shaded p5–p95 band — the standard "here's the
  forecast, here's our confidence" picture. The current box-and-whisker shows the
  10-day distribution as a single bar; the fan shows it *through time*.
- Two **compact tiles** per watchlist row: `P(up in 10d)` (this is already the
  analog **hit rate** — just surface it as a tile) and `P(vol-regime shift)` (share
  of analog days whose forward realised vol exceeds current realised vol).

**Why it fits.** Highest polish-per-effort item. The fan chart is a pure
visualisation upgrade over data `analogs_live.py` already produces; the tiles are
one-number reads ideal for a screener row and reuse existing features. No new
model, no new validation burden — the disclosure stays exactly as the watchlist's.

**How to build it here.**
- Honest version: add `ret_fwd_1d/3d/5d` to `compute_ohlcv_features` and have
  `analogs_live.py` return per-horizon percentiles → a true fan. Quick version:
  interpolate the existing 10-day band by √(h/10) and **disclose** it as an
  approximation.
- Frontend: a small SVG fan component (same inline-style approach as the reliability
  diagram); tiles slot into the existing `AssetRow`.

**Gate.** Disclosed, same as the analog watchlist.

---

## Tier 2 — transparency & governance

### 4. Bull / bear case synthesis
**From:** TradingAgents' bull/bear debate → single verdict.

**What it is.** For the selected ticker, a **case-for / case-against** panel built
by *synthesising signals the dashboard already has*, shown side by side with a
plain-language verdict and a confidence — never a black-box score. Bull column:
positive drivers (↑), hit rate > 0.5, right-skewed forward distribution, regime
alignment. Bear column: negative drivers (↓), analog **disagreement** flag, wide /
left-skewed distribution, low effective-N, poor recent calibration for that band.

**Why it fits.** It's the transparency pattern the dashboard is already reaching
for (it shows disagreement notes and drivers) but stops short of composing. It
composes *existing live outputs* — no new model, no new gate — and reads as
"reasons," which suits an advisory tool better than a single number.

**How to build it here.** A `synthesis_live.py` that consumes the already-computed
`assets`/`marketState`/`calibration` blocks and returns `{bull:[…], bear:[…],
verdict, confidence}`; a two-column panel in Overview (or a per-ticker detail).
Optionally narrated by the LLM layer when enabled (see cross-cutting).

**Gate.** Disclosed; it inherits the research-preview status of its inputs.

---

### 5. Decision change-log with rationale ("trading-as-git")
**From:** OpenAlice's stage → commit-message → guarded, hashed history.

**What it is.** When a watchlist verdict or sizing **changes materially** between
snapshots (e.g. sizing crosses a band, verdict flips bull↔bear, disagreement
toggles), record a diff with a content hash and an optional rationale, appended to
an immutable log → a "what changed and why, and when" panel. Guard checks (Kelly
cap, band validity) run before a change is accepted.

**Why it fits.** The dashboard already has the *primitives* — an append-only audit
log (`backtest_executions`) and versioned `validation_reports`. This extends the
pattern to recommendations: an auditable trail of *why a call moved*, not just its
latest state. Pure audit, advisory-only, no execution.

**How to build it here.** New `recommendation_changes` table (append-only, hashed
prev→next); write on snapshot when a material delta is detected; a compact history
panel. Reuse the audit-log conventions already in `layer0_validation/audit_log.py`.

**Gate.** Audit trail; no gate.

---

### 6. Persistent per-ticker notes "inbox"
**From:** OpenAlice's inbox (AI notes pushed to a persistent, per-asset-tagged
feed instead of vanishing into chat).

**What it is.** Replace the ephemeral, representative **alerts** panel with a
persistent, per-ticker-tagged feed that accumulates: system alerts (Layer 7
contradictions, calendar events, freshness warnings), resolved-prediction
outcomes (feature 1), and the trader's own notes. Filter by ticker; mark
read/acted.

**Why it fits.** Alerts today are throwaway mock data; making them persistent and
asset-tagged turns them into a lightweight research memory that ties the journal,
track record and watchlist together. Small, high day-to-day utility.

**How to build it here.** New `notes` table (`ticker, ts, kind, body, source,
read`); `notes_live.py`; a filterable feed panel; alert generators write into it.

**Gate.** None (a store + feed).

---

## Tier 3 — additive inputs (gated / optional)

### 7. Composite market-stress gauge (takes Layer 5 partly live)
**From:** World Monitor's 0–100 composite gauge.

**What it is.** A single top-level **market-stress** tile (0–100) rolled up from
*real* friction/macro signals the lite tier can compute — Amihud illiquidity z,
Corwin–Schultz spread proxy, VIX percentile, HY OAS — with an **explicitly
disclosed heuristic weighting** (not a validated model).

**Why it fits.** Layer 5 is currently representative; this takes it live using
signals the architecture already names (`amihud_z`, CS spread, VIX percentile,
HY OAS in `features_pit`). The composite is *presentation*, so it must ship with
the weighting shown and a "heuristic, not validated" disclosure — which is exactly
the surface-with-disclosure pattern. Do **not** dress it as a model.

**How to build it here.** `stress_live.py` computes the components from
`features_pit`, normalises to 0–100 with a transparent weight vector, returns
components + composite + the weighting for display. New gauge tile (Overview
header or a stress strip).

**Gate.** Disclosed heuristic; never `validated:true` without a real Layer-0 study.

---

### 8. Research radar (arXiv)
**From:** quant-mind's arXiv connector (its one working piece; MIT).

**What it is.** A small side panel that auto-pulls recent arXiv papers matching the
methods this system uses (regime/HMM, historical analogs, deflated Sharpe,
calibration, Kelly) and surfaces a summary feed.

**Why it fits.** Peripheral to the core evidence loop but cheap and genuinely
useful for a research-minded single trader; keeps method-tracking in the tool. Low
priority precisely because it's off the critical path.

**How to build it here.** A cached fetcher (arXiv API) + `research_radar_live.py`
+ a collapsible feed; refresh daily. The quant-mind connector can be adapted
directly (permissive licence).

**Gate.** None.

---

### 9. Kronos forecaster as a gated ensemble input
**From:** Kronos' probabilistic OHLCV model (Apache-2.0).

**What it is.** Add Kronos as an **additional** forward-return forecaster feeding
the watchlist, with uncertainty bands — an ensemble alongside the analog engine.

**Why it fits, and the caveat.** Potentially a second independent view of forward
returns, which the dashboard would present with error bars. But it is a **new
model**, and the house rule is absolute: it earns display only **after it passes
Layer 0 here** (walk-forward, CPCV, deflated Sharpe on *our* data) — the paper's
numbers don't count. Until then it stays `research_preview` or hidden. Lowest
priority because Tier-1 #3 already delivers the *visualisation* value without the
model risk, and this carries real validation + dependency weight.

**How to build it here.** `kronos_forecast_live.py` behind the existing model-gate
pattern (like `market_state_live.py` preferring a promoted artifact); register it
in the HMM-style registry; feed the fan chart when validated.

**Gate.** Validated-only. No exceptions.

---

## Cross-cutting

- **Harden the data-access contract** (TradingAgents v0.3.0). The API already
  degrades *with disclosure* (every section has a `source` flag), which honours
  the spirit. Add the missing half: an optional **strict mode** where a stale or
  missing critical feed is *refused* rather than served (surfaced via feature 2),
  plus deterministic entity resolution (ticker normalisation) in the data layer.
- **Tiered LLM fallback** (World Monitor). Only relevant once narrative panels
  exist (bull/bear case, transition notes). Wrap the existing
  `layer_llm/CachedLLMInterface` in a fallback chain (local Ollama → provider →
  lightweight) so narrative text degrades gracefully instead of failing. Stays
  behind `LLM_ENABLED`.

## Explicitly *not* pursuing (and why)

- **OpenAlice unified multi-broker account ledger / execution** — out of the
  advisory-only lane; the dashboard has no accounts and moves no money.
- **Any auto-execution / order placement** — violates the propose-never-execute
  posture (which, notably, TradingAgents shares).
- **World Monitor multi-variant apps** — low value for a single-purpose dashboard;
  if a macro-only or crypto-only lens is ever wanted, do it as a lightweight
  *watchlist profile* config, not a second app.
- **quant-mind's unbuilt pieces** (filings ingestion, knowledge graph) — not
  actually implemented upstream; nothing to lift.

## Licensing quick-reference

| Repo | Licence | Code reuse? |
|---|---|---|
| TradingAgents | MIT/Apache | Yes — patterns *and* code |
| Kronos | Apache-2.0 | Yes |
| quant-mind | permissive | Yes (the arXiv connector) |
| OpenAlice | **AGPL-3.0** | Patterns only — re-implement, don't vendor |
| World Monitor | **AGPL-3.0 + commercial-gated** | Patterns only — re-implement, don't vendor |

## Suggested sequencing

1. **Phase A (self-knowledge):** #1 system track record + #2 freshness monitor.
   Together they make the dashboard grade both its outputs and its inputs — the
   highest-leverage, most on-philosophy pair, and both mostly reuse `features_pit`.
2. **Phase B (polish + synthesis):** #3 fan chart/tiles + #4 bull/bear synthesis.
   Pure reuse of live data; big perceived-quality jump, no new validation.
3. **Phase C (governance):** #5 change-log + #6 notes inbox. Auditable "why it
   changed" + persistent research memory.
4. **Phase D (new signals, gated):** #7 stress gauge (disclosed), then #8 radar,
   then #9 Kronos (only if it clears Layer 0). Cross-cutting contract/LLM
   hardening folded in as the panels that need them land.
