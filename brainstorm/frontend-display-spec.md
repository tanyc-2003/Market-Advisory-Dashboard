# Frontend display spec — what the UI must show for the new backend

The backend now emits new sections in `GET /api/dashboard` (and two new POST
routes). **No frontend has been built for these yet** — that's deliberate; we
finish all backend logic first. This file is the running list of what each new
section needs on screen, with the exact payload contract to build against.

Consume everything through the typed client (`frontend/src/api.ts`) — add the
interfaces below to `DashboardData`, then slice into views/components as usual
(inline `CSSProperties` + `theme.ts` tokens; reuse `styles.ts` fragments and the
existing reliability-diagram / status-dot patterns).

## Status of backend sections

| Section | Backend | Payload key | Frontend |
|---|---|---|---|
| System track record | ✅ built | `trackRecord` | ⬜ to build |
| Data freshness / health | ✅ built | `dataHealth` | ⬜ to build |
| Forecast fan + prob tiles | ✅ built | `assets[].forecast/pUp/pVolShift` | ⬜ to build |
| Bull/bear case synthesis | ✅ built | `assets[].case` | ⬜ to build |
| Notes inbox | ✅ built | `notes` (+ POST) | ⬜ to build (replaces alerts) |
| Decision change-log | ⬜ backend pending | `recommendationChanges` | ⬜ |
| Composite stress gauge | ⬜ backend pending | `stress` | ⬜ |
| arXiv research radar | ⬜ backend pending | `researchRadar` | ⬜ |
| Kronos forecast | ⬜ backend pending (gated) | `assets[].kronos` | ⬜ |

Every built section carries a `source: "live" | "representative"` flag; render a
subtle "representative data" hint when not live, exactly like the existing
market-state / calibration panels.

---

## 1. System track record  →  new view **"Track record"**

Add a nav item (`data.ts` `navItems`) and a `TrackRecordView`. This is the
system grading its **own** past calls (distinct from Calibration, which grades the
trader).

**Payload**
```jsonc
"trackRecord": {
  "resolved": 210, "pending": 30,
  "hitRate": 0.538, "directionalAccuracy": 0.457,
  "meanPredP50": 0.006, "meanRealized": 0.004,
  "alphaMean": 0.002, "alphaHitRate": 0.514,
  "byTicker":    [{ "ticker": "GOOGL", "n": 42, "hitRate": 0.64, "alpha": 0.0105 }],
  "reliability": [{ "bucket": 0.5, "predicted": 0.52, "observed": 0.48, "n": 40 }],
  "source": "live"
}
```
**Show**
- **Summary cards** (reuse Calibration's card row): Resolved N (+ pending), Hit
  rate, Directional accuracy, Mean alpha vs SPY (+ alpha-hit-rate). Colour alpha
  green/red; be honest when numbers are unflattering (they will be).
- **Reliability diagram** — reuse the `CalibrationView` SVG: predicted P(up) on x,
  observed up-rate on y, diagonal = perfect. Points from `reliability`.
- **By-ticker table** — ticker · n · hit rate · alpha (green/red).
- **Empty state** (`source: "representative"`, `resolved: 0`): "No resolved calls
  yet — run `scripts/track_record.py --backfill-days 500` (or log daily) to
  populate." Don't fake numbers.

---

## 2. Data freshness / health  →  sidebar panel (or small **"Data"** view)

**Payload**
```jsonc
"dataHealth": {
  "asOf": "Jun 29, 2026", "overall": "fresh",
  "feeds": [ { "name": "NVDA", "source": "yfinance", "lastDate": "2026-06-29",
               "staleDays": 0, "pitLagDays": 0, "rows": 2500, "gaps": 0,
               "status": "fresh" } ],
  "source": "live"
}
```
**Show**
- A compact **feed list**: each row = status dot (`fresh` green / `stale` amber /
  `missing` red) + name + source + `lastDate` + "N trading days behind" when > 0.
- An **overall** badge at the top (worst feed) — promote the sidebar `asOf`
  snapshot into this. This is the PIT instinct applied to inputs.
- Best placement: a collapsible block under the sidebar snapshot, or a small
  dedicated panel. Low-chrome; it's a health readout, not a hero.

---

## 3. Forecast fan + probability tiles  →  extend the **watchlist**

New fields on each `assets[]` item (shape otherwise unchanged):
```jsonc
{ "pUp": 0.70, "pVolShift": 0.23,
  "forecast": [ { "h": 1, "p5": -0.03, "p50": 0.002, "p95": 0.04 },
                { "h": 10, "p5": -0.08, "p50": 0.018, "p95": 0.12 } ],
  "forecastApprox": true }
```
**Show**
- **Fan chart** for the selected watchlist ticker: an SVG with the median path
  (`p50` across `forecast[].h`) and a shaded `p5–p95` band widening with horizon.
  Reuse the inline-SVG approach from the reliability diagram. When
  `forecastApprox`, show a small "≈ approx" marker + tooltip ("band scaled by
  √time until per-horizon analog features are ingested").
- **Two compact tiles** in each `AssetRow`: `P↑10d` (= `pUp`) and `Δvol` (=
  `pVolShift`, "P(vol regime shift)") — one number each, status palette. `pVolShift`
  may be `null` → hide that tile.

---

## 4. Bull / bear case  →  panel near the selected-ticker sizing column

New field on each `assets[]` item:
```jsonc
"case": { "bull": ["hit rate 70%", "right-skewed forward distribution",
                    "regime: Volatile Bull", "positive Kelly (0.16)"],
          "bear": ["pct_above_ma50 ↓", "rsi_14 ↓", "ret_5d ↓"],
          "verdict": "neutral", "confidence": "moderate" }
```
**Show**
- A two-column **Case for / Case against** panel for the selected ticker: green
  column lists `bull`, red column lists `bear`, each a bullet. A **verdict pill**
  (`lean long` green / `neutral` grey / `lean short` red) + the `confidence` word.
- These are *reasons*, not a score — keep the two columns balanced and literal.

---

## 5. Notes inbox  →  replaces the ephemeral **alerts** column

**Payload**
```jsonc
"notes": {
  "unread": 3,
  "items": [ { "id": "…", "ticker": "NVDA", "createdAt": "…", "kind": "outcome",
               "source": "track_record", "body": "Resolved +2.1% vs SPY +0.4%",
               "read": false } ],
  "source": "live"
}
```
**Endpoints**
- `POST /api/notes`  body `{ body: string, ticker?: string }` → returns refreshed dashboard.
- `POST /api/notes/{id}/read` → returns refreshed dashboard (404 if unknown id).

**Show**
- A **feed** replacing the Overview "Active alerts" column: each item = kind/source
  chip + optional ticker tag + body + timestamp; unread items emphasised. Keep the
  "what this system does not know" (unknowns) column as-is.
- An **add-note input** (like the journal-close inline editor) posting to
  `/api/notes`; a **mark-read** affordance per item posting to `/read`.
- Filter by ticker / unread; show the `unread` count as a badge on the nav/section.

---

## api.ts additions (summary)

```ts
export interface TrackRecord {
  resolved: number; pending: number
  hitRate: number | null; directionalAccuracy: number | null
  meanPredP50: number | null; meanRealized: number | null
  alphaMean: number | null; alphaHitRate: number | null
  byTicker: { ticker: string; n: number; hitRate: number; alpha: number | null }[]
  reliability: { bucket: number; predicted: number; observed: number; n: number }[]
  source?: string
}
export interface DataFeed {
  name: string; source: string; lastDate: string
  staleDays: number; pitLagDays: number; rows: number; gaps: number
  status: 'fresh' | 'stale' | 'missing'
}
export interface DataHealth { asOf: string | null; overall: string; feeds: DataFeed[]; source?: string }
export interface ForecastPoint { h: number; p5: number; p50: number; p95: number }
export interface AssetCase { bull: string[]; bear: string[]; verdict: string; confidence: string }
export interface NoteItem {
  id: string; ticker: string | null; createdAt: string
  kind: string; source: string; body: string; read: boolean
}
export interface NotesData { unread: number; items: NoteItem[]; source?: string }
// extend Asset: pUp?: number; pVolShift?: number | null; forecast?: ForecastPoint[]; forecastApprox?: boolean; case?: AssetCase
// extend DashboardData: trackRecord: TrackRecord; dataHealth: DataHealth; notes: NotesData
// new client fns: postNote(body, ticker?), markNoteRead(id)
```

## Pending sections (build frontend after their backend lands)
`recommendationChanges` (change-log timeline), `stress` (0–100 gauge tile with
displayed weights + heuristic disclosure), `researchRadar` (collapsible paper
feed), `assets[].kronos` (second fan band, only when validated). See
[tier-2-spec.md](tier-2-spec.md) and [tier-3-spec.md](tier-3-spec.md).
