# Market Advisory — Frontend (React + Vite)

React + Vite + TypeScript implementation of the **Market Advisory** dashboard,
recreating the Claude Design mock (`Market Advisory.dc.html`) pixel-for-pixel.
This is the successor UI to the Streamlit app under
`src/advisory/dashboard/`; the Python layers remain the computation backend.

## Prerequisites

- **Node.js ≥ 18** and npm (frontend).
- **Python ≥ 3.11** with the API extra installed (backend):
  `pip install -e ".[api]"` from the repo root.

## Getting started

Run the **backend API** and the **frontend** together (two terminals):

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
  App.tsx             # layout shell + view state (which page is active)
  theme.ts            # design tokens (colours, fonts) + formatting helpers
  styles.ts           # shared, typed CSSProperties fragments
  api.ts              # typed fetch client + payload types (GET /api/dashboard, POST /api/journal)
  data.ts             # TypeScript shapes + UI copy (nav, header) — values come from the API
  components/
    Sidebar.tsx       # brand, nav, snapshot panel
    Header.tsx        # per-view header + production/preview gate pills
  views/
    OverviewView.tsx    # Layer 0 gate strip, Layer 1 market state, Layer 10 sizing,
                        # Layers 2·3·7 watchlist, Layer 7 alerts, "unknowns"
    PortfolioView.tsx   # Layer 6 weights, stress test, correlation cluster
    JournalView.tsx     # open/closed trades + new-entry form
    CalibrationView.tsx # Brier/ECE cards, reliability diagram, calibration table
    ValidationView.tsx  # Layer 0 sign-off table + survivorship / DSR summaries
```

## Backend wiring

The dashboard is wired to a FastAPI backend (`src/advisory/api/`). On load the
app fetches `GET /api/dashboard` (one round trip) via the typed client in
`src/api.ts`; the journal form posts to `POST /api/journal`, which persists the
entry to DuckDB and returns the refreshed payload.

What's genuinely live vs. representative:

- **Live now:** run mode / settings, Kelly cap, survivorship coverage (computed
  from seeded features), the DSR audit trial count, and the **trade journal**
  (the Log-entry form writes to `journal_entries`; logging the first trade flips
  the sidebar from "representative" to live).
- **Representative (server-side, single source of truth in
  `src/advisory/api/presentation.py`):** market state, analogs/watchlist,
  sizing, calibration, portfolio/stress, alerts. Each can be swapped to live
  compute one endpoint at a time without touching the frontend — the validation
  gate already overlays any persisted `ValidationReport`s automatically.

`src/data.ts` now holds only the TypeScript shapes (and UI copy); the values
come from the API. To point at a non-default API, set `VITE_API_BASE`.

## Design fidelity notes

- Dark "evidence-gated" theme: bg `#101319`, cards `#161a21`, IBM Plex Sans/Mono.
- Status colours: production `#5fbf7f`, research preview `#e0b04a`,
  blocked `#e06c6c`, no-report `#6b7480`.
- The Query (LLM) nav item is intentionally disabled/`OFF`, matching the design
  and the `LLM_ENABLED` gate in the Streamlit app.
