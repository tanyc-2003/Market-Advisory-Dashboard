# Market Advisory — Frontend (React + Vite)

React + Vite + TypeScript implementation of the **Market Advisory** dashboard,
recreating the Claude Design mock (`Market Advisory.dc.html`) pixel-for-pixel.
This is the successor UI to the Streamlit app under
`src/advisory/dashboard/`; the Python layers remain the computation backend.

## Prerequisites

- **Node.js ≥ 18** and npm. (Node was not installed when this was scaffolded —
  install it from <https://nodejs.org> first.)

## Getting started

```bash
cd frontend
npm install
npm run dev      # starts Vite on http://localhost:5173
```

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
  data.ts             # all domain data + types (the only place to swap for an API)
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

## Connecting to the backend (later)

Every view consumes **typed data** from `src/data.ts`, which currently holds the
static mock values from the design. To go live, replace the exported constants
with `fetch()` calls to a thin HTTP API over the existing Python service layer
(`src/advisory/dashboard/services.py`) — the component code does not need to
change. The shapes in `data.ts` (e.g. `Layer`, `Asset`, `CalRow`) map directly
onto what `list_layer_status_rows`, the analog engine, and the journal store
already return.

## Design fidelity notes

- Dark "evidence-gated" theme: bg `#101319`, cards `#161a21`, IBM Plex Sans/Mono.
- Status colours: production `#5fbf7f`, research preview `#e0b04a`,
  blocked `#e06c6c`, no-report `#6b7480`.
- The Query (LLM) nav item is intentionally disabled/`OFF`, matching the design
  and the `LLM_ENABLED` gate in the Streamlit app.
