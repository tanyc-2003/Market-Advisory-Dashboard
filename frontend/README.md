# Market Advisory — Frontend (React + Vite)

React + Vite + TypeScript implementation of the **Market Advisory** dashboard,
recreating the Claude Design handoff (`Market Advisory.dc.html`) pixel-for-pixel.
This is the current UI; the Streamlit app under `src/advisory/dashboard/` is the
legacy UI it supersedes, and the Python layers remain the computation backend.

## Prerequisites

- **Node.js ≥ 18** and npm (frontend).
- **Python ≥ 3.11** with the API extra installed (backend):
  `pip install -e ".[api]"` from the repo root.

## Getting started

The easiest path on Windows is the repo-root launcher **`run_dashboard.bat`**
(double-click) — it starts the API and the frontend, each in its own window. To
run them by hand (two terminals):

```bash
# terminal 1 — API (repo root)
pip install -e ".[api]"
python scripts/run_api.py            # FastAPI on http://localhost:8000

# terminal 2 — frontend
cd frontend
npm install
npm run dev                          # Vite on http://localhost:5173
```

Vite proxies `/api/*` to the API (see `vite.config.ts`), so the dashboard loads
its data from the backend with no CORS setup in dev. If the API isn't running,
the app shows an error screen with a Retry button.

Other scripts:

```bash
npm run build      # production build to dist/
npm run preview    # serve the production build locally
npm run typecheck  # tsc --noEmit
```

## Structure

```
src/
  main.tsx            # React entry
  App.tsx             # layout shell + view state; fetches /api/dashboard; polls while a ticker is ingesting
  theme.ts            # design tokens (colours, fonts) + formatting/SVG helpers (fmtPct, buildFan, status colours)
  styles.ts           # shared, typed CSSProperties fragments
  api.ts              # typed fetch client + payload types (dashboard, journal, notes, watchlist)
  data.ts             # TypeScript shapes + UI copy (nav, headers) — values come from the API
  components/
    Sidebar.tsx       # brand, nav, snapshot, collapsible Data health + Research radar, disclosure
    Header.tsx        # per-view header + production/preview gate pills
  views/
    OverviewView.tsx    # stress gauge, Layer 0 gate strip, market state + sizing + bull/bear case,
                        # forecast fan, watchlist (add ticker, P↑/Δvol tiles, distribution track),
                        # notes inbox, "what this system does not know", decision change-log
    TrackRecordView.tsx # self-grading cards + reliability diagram + by-ticker table (Tier 1 #1)
    PortfolioView.tsx   # Layer 6 weights, stress test, correlation cluster
    JournalView.tsx     # open/closed trades + new-entry form
    CalibrationView.tsx # Brier/ECE cards, reliability diagram, calibration table
    ValidationView.tsx  # Layer 0 sign-off table + survivorship / DSR summaries
```

## Views

Six views (the Query/LLM item is disabled/`OFF`, matching `LLM_ENABLED`):

- **Overview** — the main screen. Composite market-stress gauge, the Layer 0 gate
  strip, market state (Layer 1) + Kelly sizing (Layer 10) + bull/bear case, the
  per-ticker forecast fan, the watchlist (Layers 2·3·7) with add-a-ticker, the
  Layer 7 notes inbox, the "unknowns" panel, and the decision change-log.
- **Track record** — the system grading its *own* past calls (distinct from
  Calibration, which grades the trader).
- **Portfolio**, **Journal**, **Calibration**, **Validation** — as their names say.

## Backend wiring

On load the app fetches `GET /api/dashboard` (one round trip) via the typed
client in `src/api.ts`. Mutations return the refreshed payload, which `App` swaps
into state:

- `POST /api/journal`, `POST /api/journal/{id}/close` — log / close a trade.
- `POST /api/notes`, `POST /api/notes/{id}/read` — notes inbox.
- `POST /api/recommendations/{ticker}/rationale` — attach a "commit message".
- `POST /api/watchlist/{ticker}`, `DELETE /api/watchlist/{ticker}` — **add / remove
  a watchlist ticker**. An added ticker returns `pending` and is ingested
  asynchronously; the SPA **polls `/api/dashboard` every 4s** while any ticker is
  pending, so the row fills in on its own.

What's genuinely live vs. representative (full matrix in
[../docs/10_web_stack.md](../docs/10_web_stack.md)):

- **Live:** run mode / settings, Kelly cap, survivorship coverage, DSR audit
  count; the **trade journal** incl. trade-close; **market state** from a
  real-data HMM (Layer 1); the **watchlist analogs + sizing** (Layers 2 / 10);
  **calibration** graded from closed journal entries (Layer 9); and the Tier 1–3
  enhancement sections (track record, data health, stress gauge, notes, change-log,
  research radar) computed by the `*_live.py` modules. The lite models carry a
  research-preview disclosure — they don't clear Layer 0 predictive sign-off.
- **Representative (server-side default in `src/advisory/api/presentation.py`):**
  portfolio (Layer 6) and any section whose store/model is absent — so a panel is
  never empty. Each live section carries a `source` flag.

The Kronos forecast fan attaches only when a **promoted** (Layer-0-passed) Kronos
model exists; it currently stays hidden by design (see
[../docs/kronos_finetune.md](../docs/kronos_finetune.md)).

`src/data.ts` holds only the TypeScript shapes (and UI copy); the values come from
the API. To point at a non-default API, set `VITE_API_BASE`. To make the live
panels real, run the data pipeline in
[../docs/10_web_stack.md](../docs/10_web_stack.md#enabling-live-data).

## Design fidelity notes

- Dark "evidence-gated" theme: bg `#101319`, cards `#161a21`, IBM Plex Sans/Mono.
- Status colours: production `#5fbf7f`, research preview `#e0b04a`,
  blocked `#e06c6c`, no-report `#6b7480`.
- The Query (LLM) nav item is intentionally disabled/`OFF`, matching the design
  and the `LLM_ENABLED` gate in the Streamlit app.
