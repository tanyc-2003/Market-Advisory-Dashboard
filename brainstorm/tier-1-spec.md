# Tier 1 — implementation specs

Build-first features. All three reuse `features_pit` and the existing
`presentation.py` + `*_live.py` + `/api/dashboard` seam, so they slot into the
current architecture without new infrastructure. See
[feature-roadmap.md](feature-roadmap.md) for the rationale.

Conventions used throughout (already in the codebase):
- **DDL** lives only in `src/advisory/data_infra/schema.py` (add a constant,
  register it in `bootstrap_schema`). Idempotent `CREATE TABLE IF NOT EXISTS`.
- **Live modules** are `src/advisory/api/<section>_live.py` with a
  `compute_<section>(conn) -> dict | None` (return `None` → representative
  fallback). Wired via a thin helper in `live.py` and into `build_dashboard()`.
- **Payload** keys are camelCase (map 1:1 to `frontend/src/api.ts`). Each live
  section carries a `source: "live" | "representative"` flag.
- **Frontend** views take a typed slice as props; inline `CSSProperties` with
  tokens from `theme.ts`; shared fragments from `styles.ts`.
- **Verification** (per feature): a `TestClient`/temp-DuckDB unit test of the
  compute function + a real-HTTP e2e via `MAIN_DB_PATH` pointing at a throwaway
  DB. Frontend `npm run typecheck` + `build`.

---

## 1. System self-grading track record  *(flagship)*

**Outcome.** A panel where the *system* grades its own past watchlist calls:
rolling hit rate, predicted-vs-realised, alpha vs. SPY, and a reliability curve —
turning static "deflated Sharpe < floor" disclaimers into empirical ones.

### Data model — new table
`schema.py`:
```sql
CREATE TABLE IF NOT EXISTS system_predictions (
    prediction_id   VARCHAR PRIMARY KEY,   -- sha1(ticker|knowledge_date|horizon)
    ticker          VARCHAR NOT NULL,
    knowledge_date  DATE    NOT NULL,       -- as-of date the call was emitted (PIT)
    horizon_days    INTEGER NOT NULL DEFAULT 10,
    pred_p50        DOUBLE,                 -- predicted median forward return
    pred_p5         DOUBLE,
    pred_p95        DOUBLE,
    pred_hit_prob   DOUBLE,                 -- predicted P(up) = analog hit rate
    pred_sizing     DOUBLE,                 -- displayed Kelly at emit time
    effective_n     DOUBLE,
    realized_ret    DOUBLE,                 -- filled at resolution
    benchmark_ret   DOUBLE,                 -- SPY forward return over same window
    alpha           DOUBLE,                 -- realized_ret - benchmark_ret
    resolved        BOOLEAN NOT NULL DEFAULT FALSE,
    resolved_at     DATE
);
```

### Backend
**Emit** — in `analogs_live.py`, when a watchlist is computed, append one row per
ticker with `knowledge_date = max(effective_date)` and `prediction_id` a hash of
`(ticker, knowledge_date, horizon)`. Use `INSERT ... ON CONFLICT DO NOTHING`
(DuckDB) so re-computing the same day is idempotent. This is the only write on the
read path; keep it inside `db.LOCK` and cheap.

**Resolve** — `scripts/resolve_predictions.py` (also callable from the API lazily):
for each `resolved = FALSE` row whose `knowledge_date + horizon_days` business days
`<= max(effective_date)` in `features_pit` (i.e. the window has fully elapsed):
- `realized_ret = features_pit(ticker, 'ret_fwd_10d', knowledge_date)` — this
  value *is* the realised forward return, only knowable at T+10, so reading it
  after the window elapses is PIT-honest.
- `benchmark_ret = features_pit('SPY', 'ret_fwd_10d', knowledge_date)`.
- `alpha = realized_ret - benchmark_ret`; set `resolved = TRUE`, `resolved_at`.

**Read** — `track_record_live.py::compute_track_record(conn)`:
- Pull resolved rows; if `< MIN_RESOLVED` (start at 20) return `None`.
- Aggregate: `hitRate` (realised>0), `meanPredP50`, `meanRealized`, `alphaMean`,
  `alphaHitRate` (alpha>0); a `reliability` series bucketing `pred_hit_prob` into
  deciles vs. observed hit; a `byTicker` breakdown; `pending` = unresolved count.
- Wire `track_record(conn)` helper into `build_dashboard()` (try live → else a
  representative sample from `presentation.track_record()`).

### API payload
```jsonc
"trackRecord": {
  "resolved": 128, "pending": 15,
  "hitRate": 0.54, "meanPredP50": 0.012, "meanRealized": 0.008,
  "alphaMean": 0.003, "alphaHitRate": 0.51,
  "byTicker":    [{ "ticker": "NVDA", "n": 30, "hitRate": 0.6, "alpha": 0.004 }],
  "reliability": [{ "bucket": 0.55, "observed": 0.52, "n": 40 }],
  "source": "live"
}
```

### Frontend
- `api.ts`: add `TrackRecord` interface + field on `DashboardData`.
- New view `views/TrackRecordView.tsx` + nav item in `data.ts` (`navItems`), or a
  section appended to `ValidationView`. Reuse the reliability-diagram SVG from
  `CalibrationView`; add a summary card row (`hitRate`, `alphaMean`, resolved N)
  and a `byTicker` table. Same styling primitives.

### Gate & disclosure
Ships **disclosed** with a small-sample note (`resolved < 60` → "early sample").
Strengthens automatically as calls resolve. Once a ticker/engine has enough
resolved calls it can feed a real `ValidationReport` (future Layer-0 tie-in).

### Edge cases
- No SPY in `features_pit` → alpha `null`, hide the alpha tiles (still show hit
  rate). Prediction with `null` realized (data gap) → leave unresolved.
- Ticker leaves the watchlist → its historical predictions still resolve/appear.

### Effort: **M.** No new model. Order within tier: build first (others don't
depend on it, but it's the highest-value gap-filler).

---

## 2. Data freshness & PIT health monitor

**Outcome.** A meta-panel that grades *inputs* the way Layer 0 grades outputs:
per feed, last date, staleness, missing-bar fraction, PIT lag; stale feeds flagged
and their dependent panels inherit a "stale input" disclosure.

### Data model
**None new** — reuse `features_pit` (dates, counts) and `yfinance_fetch_audit`
(`status`, `n_bad_rows`, `n_consec_gaps`, `fetched_at`).

### Backend — `data_health_live.py::compute_data_health(conn)`
- **Equities / VIX (`source='yfinance'`):** per ticker `max(effective_date)`,
  `max(knowledge_date)`, row count; join latest `yfinance_fetch_audit` row for
  status/gap stats.
- **Macro (`source='fred'`):** per derived series (`yield_curve_slope`,
  `hy_spread_roc_21d`) `max(effective_date)`.
- For each feed compute `staleDays` = business days between its last date and
  `max(effective_date)` across the DB (the effective "today" of the dataset);
  classify `fresh` (≤2), `stale` (≤5), `missing` (>5 or no rows). `pitLagDays` =
  `knowledge_date − effective_date`.
- `overall` = worst feed status. Return `None` only if `features_pit` is empty.

### API payload
```jsonc
"dataHealth": {
  "asOf": "Jun 29, 2026", "overall": "fresh",
  "feeds": [
    { "name": "NVDA", "source": "yfinance", "lastDate": "2026-06-29",
      "staleDays": 0, "missingBarFraction": 0.0, "pitLagDays": 0, "status": "fresh" }
  ],
  "source": "live"
}
```

### Frontend
Compact panel — either a collapsible block in the **sidebar** (extends the existing
`asOf` snapshot) or a small **Data** view. Each feed = one row with a status dot
(green/amber/red reusing the status palette). Promote the old Streamlit
`is_data_stale` banner into this per-feed view.

### Cross-cutting hook — strict mode
Add `STRICT_FRESHNESS: bool = False` to `config/settings.py`. When true and a
*critical* feed (equities or VIX) is `missing`, the dependent live sections
(market state, watchlist) attach a `disclosure` ("inputs stale — computed on data
N days old") or, hardest setting, refuse and fall back to representative. This is
the "reject, don't silently serve" half of the TradingAgents data contract.

### Gate: meta-panel, no model gate — but it *governs* the others.
### Effort: **S–M.** Mostly SQL over existing tables.

---

## 3. Forecast fan chart + compact probability tiles

**Outcome.** A per-ticker forecast fan (median path + shaded p5–p95 band through
time) and two one-number tiles per watchlist row — all model-agnostic, driven by
data `analogs_live.py` already produces.

### Data model
Optional feature additions for the honest fan (see below): `ret_fwd_1d`,
`ret_fwd_3d`, `ret_fwd_5d` in `compute_ohlcv_features`
(`data_infra/features.py`); requires a re-ingest. No schema change (features are
rows in `features_pit`).

### Backend — extend `analogs_live.py`
Per asset, add:
- `forecast`: per-horizon percentiles of the analog set's forward returns.
  - **Honest:** compute analog distributions at horizons {1,3,5,10} from the new
    `ret_fwd_h` features → `[{ "h":1,"p5","p50","p95" }, …]`.
  - **Quick (fallback):** interpolate the existing 10-day band by `√(h/10)` and set
    `"approx": true` so the UI discloses it.
- `pUp`: `= hitRate` (already computed — just surface it).
- `pVolShift`: share of analog days whose forward realised vol exceeds the
  ticker's current `realized_vol_21d` (needs a fwd-vol feature or a proxy; disclose
  if proxied).

### API payload (additions to each `assets[]` item)
```jsonc
{ "...": "existing asset fields",
  "pUp": 0.62, "pVolShift": 0.34,
  "forecast": [ { "h": 1, "p5": -0.02, "p50": 0.003, "p95": 0.02 },
                { "h": 10, "p5": -0.08, "p50": 0.018, "p95": 0.12 } ],
  "forecastApprox": false }
```

### Frontend
- **Fan chart:** new SVG component (same inline-style approach as the calibration
  reliability diagram) rendered for the selected watchlist ticker — historical
  price line + median path + shaded band. Slots into the Overview watchlist detail
  or the sizing column.
- **Tiles:** two compact readouts in `AssetRow` (`P↑10d`, `Δvol`), each one number
  with the status palette. `forecastApprox` → a small "≈" marker + tooltip.

### Gate: **disclosed**, inherits the watchlist's research-preview status.
### Effort: **S–M** (quick approx) / **M** (honest, needs re-ingest). The tiles are
**S** on their own and worth shipping first (they're pure surfacing of existing
numbers).

---

## Tier-1 definition of done
- [ ] `system_predictions` table + emit + resolver + `track_record_live` + panel;
      unit test on temp DB, HTTP e2e, typecheck/build.
- [ ] `data_health_live` + panel + optional `STRICT_FRESHNESS`; e2e shows a stale
      feed flagged.
- [ ] Fan chart + `pUp`/`pVolShift` tiles; approx path disclosed when used.
- [ ] All three carry a `source` flag and fall back to representative with no DB.
