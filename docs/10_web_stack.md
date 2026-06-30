# 10 — Web stack: React frontend + HTTP API

This document describes the **web delivery layer** that sits in front of the
layered Python backend: a React + Vite single-page app talking to a thin FastAPI
service. It supersedes the Streamlit dashboard ([07_dashboard.md](07_dashboard.md))
as the primary UI; the Streamlit app remains in the tree, untouched, for
reversibility.

Nothing here changes the [Layer 0 invariant](01_overview.md) or the layer
contracts in [04_layers.md](04_layers.md). The web stack is a *read/serialise*
surface over the same DuckDB stores and layer modules.

---

## Topology

```
  Browser
    │  (loads the SPA, then fetches JSON)
    ▼
  React + Vite SPA  ── frontend/src ──────────────────────────────┐
    │   App.tsx fetches GET /api/dashboard on mount;               │
    │   journal form POSTs; views render typed slices.             │
    ▼                                                              │
  /api/*  (Vite dev proxy → :8000, or same-origin in prod)        │
    ▼                                                              │
  FastAPI app  ── src/advisory/api/app.py ───────────────────────┐│
    │                                                             ││
    │  live.build_dashboard()  assembles one payload:             ││
    │    ├─ meta / gate / survivorship / DSR   (real wiring)       ││
    │    ├─ market_state_live.py   → Layer 1 HMM   (live)          ││
    │    ├─ analogs_live.py        → Layers 2 + 10 (live)          ││
    │    ├─ calibration_live.py    → Layer 9        (live)         ││
    │    ├─ journal (JournalStore)                  (live)         ││
    │    └─ presentation.py        → everything else (representative)
    ▼                                                              ││
  DuckDB main.duckdb + audit.duckdb   +   models/hmm_v7_lite*.pkl  ◄┘
    ▲
  Data pipeline:  ingest_real_data.py → train_hmm.py → validate_hmm_candidate.py
```

The API never computes a layer's *validated* output on the fly — it reads what
the stores and trained artifacts already contain, exactly like the Streamlit
dashboard. The difference is transport (JSON over HTTP) and presentation (React).

---

## The HTTP API (`src/advisory/api/`)

| Module | Responsibility |
|---|---|
| `app.py` | FastAPI app, CORS, request models, the four routes |
| `live.py` | Assembles the dashboard payload; per-section live wiring + fallback |
| `presentation.py` | Server-side representative data (single source of truth) |
| `db.py` | One shared DuckDB connection behind a reentrant lock |
| `market_state_live.py` | Layer 1 — regime occupancy from the trained HMM |
| `analogs_live.py` | Layers 2 + 10 — analog distributions + Kelly ladder |
| `calibration_live.py` | Layer 9 — reliability graded from closed journal entries |

### Routes

| Method · path | Purpose |
|---|---|
| `GET /api/health` | Liveness probe (`{"status":"ok"}`) |
| `GET /api/dashboard` | The whole dashboard in one payload (see below) |
| `POST /api/journal` | Append a journal entry; returns the refreshed dashboard |
| `POST /api/journal/{id}/close` | Close an open trade (exit P&L, reason, validated); returns the refreshed dashboard |

The SPA loads `/api/dashboard` once on mount, so a page render is a single round
trip. The two journal routes return the *refreshed* dashboard so the client can
replace its state without a second fetch.

### The `/api/dashboard` payload

```jsonc
{
  "meta":   { "asOf", "appMode", "developerMode", "llmEnabled",
              "kellyCap", "gate": { "production", "preview" }, "live" },
  "layers": [ { "id","name","status","sharpe","ece","p30","dsr","rationale" }, … ],
  "marketState": { "states":[{ "name","prob" }], "uncertainty",
                   "transition", "source", "validated", "disclosure" },
  "assets": [ { "ticker","sector","n","hitRate","conf",
                "p5","p25","p50","p75","p95",
                "disagreement","disagreementNote?","drivers",
                "sizing":{ "raw","std","regime","displayed" } }, … ],
  "alerts": [ { "sev","title","detail" } ],
  "unknowns": [ "…" ],
  "sizingNote": "…",
  "portfolio": { "weights","effectiveN","scenarios","stressMap","stressNote","cluster" },
  "journal":  { "open":[{ "id","ticker","direction","conf","thesis","opened" }],
                "closed":[{ "ticker","direction","outcome","pnl" }] },
  "calibration": { "cards","rows","drift","driftDetected","source" },
  "validation":  { "survivorshipCoverage","dsrTrials" }
}
```

Keys are **camelCase** so the payload maps directly onto the frontend's
TypeScript types (`frontend/src/api.ts`) with no transformation layer.

### Connection management

DuckDB rejects a second read-write connection while one is open, and FastAPI
runs sync handlers in a threadpool. So `db.py` keeps **one** shared connection
behind a reentrant lock (`db.LOCK`); every DB section of a request holds it. When
`main.duckdb` is absent, reads return `None` and the API falls back to
representative data; the journal write path bootstraps the schema on demand, so
journaling works even on a machine that never ran a seed script.

---

## Live vs representative

Every section degrades gracefully: it serves **live** data computed from real
stores/artifacts when they exist, and falls back to a **representative** payload
from `presentation.py` otherwise — never an empty or broken panel. `meta.live`
and per-section `source` flags tell the client which it received.

| Dashboard section | Live source | When live | Fallback |
|---|---|---|---|
| Mode, Kelly cap, gate counts | `config.settings` + layer count | always | — |
| Survivorship coverage | `SurvivorshipAuditor` over seeded features | features present | `"0.971"` |
| DSR audit trials | `AuditLog.trial_count()` | `audit.duckdb` present | `"3,184"` |
| **Market state** (Layer 1) | `market_state_live.py` — HMM regime occupancy | model + features present | representative |
| **Watchlist + sizing** (Layers 2, 10) | `analogs_live.py` — analog distributions + Kelly | per-ticker features present | representative |
| **Journal** (Layer 8) | `JournalStore` (real CRUD) | ≥1 logged entry | representative sample |
| **Calibration** (Layer 9) | `calibration_live.py` — graded closed entries | ≥5 graded entries | representative |
| Validation gate metrics (Layer 0) | overlays persisted `ValidationReport`s | report rows exist | representative rows |
| Portfolio / stress (Layer 6), alerts (Layer 7) | — | — | representative |

### The "surface with disclosure" rule

The lite-tier models do **not** clear Layer 0 predictive sign-off (e.g. the HMM's
walk-forward Sharpe is well under the 0.5 floor). Rather than hide them, the API
surfaces the live output **with an explicit research-preview disclosure** — the
`marketState.disclosure` banner, the watchlist's research-preview strip, and the
sizing panel's "not validated for live decision support" note. This mirrors the
backend philosophy in [03_invariants.md](03_invariants.md): degrade visibly,
never silently. A section only claims `validated: true` when its **promoted**
artifact is in place.

---

## Enabling live data

Live sections need the DuckDB stores and (for Layer 1/2) a trained HMM. Run once
from the repo root:

```bash
pip install -e ".[api]"                 # adds fastapi + uvicorn

python scripts/ingest_real_data.py      # yfinance OHLCV/VIX + FRED macro (free, no key)
python scripts/train_hmm.py --mode v7_lite          # fits the lite HMM → models/hmm_v7_lite_<date>.pkl
# optional: promote on predictive sign-off (will not promote if WF-Sharpe < floor)
python scripts/validate_hmm_candidate.py --candidate models/hmm_v7_lite_<date>.pkl --promote-on-pass
```

Notes:
- The default ingest universe includes the macro factor proxies plus
  NVDA / MSFT / AAPL / GOOGL / AMZN — those single names become the live
  watchlist. Add others with `--tickers`.
- Generated `models/*.pkl` and `data/db/*.duckdb` are git-ignored.
- Free data has no clean delisted-tickers feed, so survivorship cannot be
  *audited* against real data; this is the architecturally correct degradation
  (see the README's real-data note).

`market_state_live.py` prefers the promoted canonical model
(`models/hmm_v7_lite.pkl`); if only a dated candidate exists it uses the newest
one and marks the result `validated: false`.

---

## The frontend (`frontend/`)

React 18 + Vite + TypeScript. Styling is inline `CSSProperties` mirroring the
design's exact tokens — no CSS framework. See [frontend/README.md](../frontend/README.md)
for the run/build commands.

```
frontend/src/
  main.tsx           # React entry
  App.tsx            # layout shell + view state; fetches /api/dashboard; loading/error screens
  api.ts             # typed fetch client + payload types (the API contract, client side)
  data.ts            # TypeScript shapes + UI copy (nav, headers) — values come from the API
  theme.ts           # design tokens (colours, fonts) + formatting helpers
  styles.ts          # shared typed style fragments
  components/        # Sidebar, Header
  views/             # Overview, Portfolio, Journal, Calibration, Validation
```

Data flow:
1. `App.tsx` calls `fetchDashboard()` on mount → shows a loading screen, then the
   layout, or an error screen with a Retry button if the API is unreachable.
2. The single `DashboardData` object is sliced and passed to the five views as
   props. No view fetches on its own.
3. The journal form calls `postJournalEntry()` / `closeJournalEntry()`, which
   return the refreshed dashboard; `App` swaps it into state.

Config:
- Dev: `vite.config.ts` proxies `/api` → `http://localhost:8000`, so the SPA uses
  same-origin paths with no CORS setup.
- Override the API base with the `VITE_API_BASE` env var for other deployments.

---

## Running it

Two processes (two terminals):

```bash
# terminal 1 — API (repo root)
python scripts/run_api.py            # FastAPI on http://localhost:8000

# terminal 2 — frontend
cd frontend && npm install && npm run dev   # Vite on http://localhost:5173
```

Open `http://localhost:5173`. With no DuckDB/model present the dashboard renders
entirely from representative data (and the sidebar says so); after the ingest +
train pipeline above, the market-state, watchlist, sizing and (once you close
journal trades) calibration panels switch to live.

---

## Extending: taking another section live

The portfolio/stress (Layer 6) and alerts (Layer 7) panels are still
representative. The pattern to take one live is fixed:

1. Add `src/advisory/api/<section>_live.py` with a `compute_<section>(conn)` that
   reads real stores / layer modules and returns the section's payload shape, or
   `None` to fall back.
2. In `live.py`, add a thin `<section>(conn)` helper that tries the live module
   inside `try/except` and falls back to `presentation.<section>()`, tagging the
   representative branch with `source: "representative"`.
3. Wire it into `build_dashboard()` and the returned payload.
4. If the live output is not Layer-0 signed off, attach a `disclosure` and render
   a research-preview banner in the matching view.

No frontend type change is needed unless the payload gains fields — the existing
views render whatever the API returns for their slice.

---

## Cross-references

- Backend layer flow and the Layer 0 gate: [02_architecture.md](02_architecture.md)
- Per-layer public APIs the live modules call: [04_layers.md](04_layers.md)
- The invariants the disclosures uphold: [03_invariants.md](03_invariants.md)
- The legacy Streamlit UI this supersedes: [07_dashboard.md](07_dashboard.md)
- V7_lite modes and degradations: [09_v7_lite.md](09_v7_lite.md)
