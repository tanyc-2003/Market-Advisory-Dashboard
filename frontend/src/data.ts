/**
 * Shared types + static UI copy for the dashboard.
 *
 * Domain *values* (layers, market state, watchlist, sizing, portfolio, journal,
 * calibration, validation summaries) are no longer defined here — they are
 * fetched from the API (see `src/api.ts`, backed by `src/advisory/api/`). This
 * module now holds only the TypeScript shapes those payloads conform to, plus
 * client-side UI concerns (navigation, per-view header copy).
 */
import type { LayerStatus, ForecastBand } from './theme'

// ---------- domain types (mirror the API payload) ----------

export interface Layer {
  id: string
  name: string
  status: LayerStatus
  sharpe: number | null
  ece: number | null
  p30: number | null
  dsr: number | null
  rationale: string
}

export interface MarketStateRow {
  name: string
  prob: number
}

export interface Sizing {
  raw: number
  std: number
  regime: number
  displayed: number
}

export interface CaseData {
  bull: string[]
  bear: string[]
  verdict: string
  confidence: string
}

export interface Asset {
  ticker: string
  sector: string
  n: number
  hitRate: number
  conf: string
  p5: number
  p25: number
  p50: number
  p75: number
  p95: number
  disagreement: boolean
  disagreementNote?: string
  drivers: string[]
  sizing: Sizing
  /** P(up in 10d) from the analog engine; may be absent for representative rows. */
  pUp?: number | null
  /** P(vol-regime shift). */
  pVolShift?: number | null
  /** Per-horizon forecast fan; when absent the Overview interpolates a √t approx. */
  forecast?: ForecastBand[]
  /** true when the fan is a √t approximation rather than per-horizon analogs. */
  forecastApprox?: boolean
  /** Bull/bear synthesis (Tier 2 #4); attached by synthesis_live. */
  case?: CaseData
}

export interface Alert {
  sev: 1 | 2 | 3
  title: string
  detail: string
}

export interface Weight {
  ticker: string
  w: number
}

export interface StressData {
  vol: number
  base: number
  factors: Array<[string, string]>
}

export interface OpenTrade {
  /** Real DuckDB entry id; empty string for representative (un-closable) rows. */
  id: string
  ticker: string
  direction: string
  conf: number
  thesis: string
  opened: string
}

export interface ClosedTrade {
  ticker: string
  direction: string
  outcome: string
  pnl: string
}

export interface CalRow {
  band: string
  implied: number
  observed: number
  lo: number
  hi: number
  n: number
}

// ---------- enhancement-section types (Tiers 1–3) ----------

export interface Feed {
  name: string
  source?: string
  lastDate?: string
  staleDays: number
  status: string
}

export interface DataHealth {
  asOf: string | null
  overall: string
  feeds: Feed[]
  source?: string
}

export interface ResearchItem {
  topic: string
  title: string
  authors: string
  published?: string
  url: string
  summary?: string
}

export interface ResearchRadar {
  fetchedAt: string | null
  items: ResearchItem[]
  source?: string
}

export interface StressComponent {
  name: string
  value: number
  weight: number
}

export interface Stress {
  composite: number | null
  level: string
  components: StressComponent[]
  weighting: string | null
  validated?: boolean | null
  source?: string
}

export interface NoteItem {
  id: string
  ticker: string | null
  kind: string
  body: string
  source: string
  read: boolean
  createdAt: string
}

export interface NotesData {
  unread: number
  items: NoteItem[]
  source?: string
}

export interface RecChange {
  id?: string
  ticker: string
  field: string
  prev: string
  /** API sends `new`; the design calls it `next`. Either may be present. */
  next?: string
  new?: string
  verdict?: string
  changedAt: string
  guardPassed: boolean
}

export interface RecommendationChanges {
  items: RecChange[]
  source?: string
}

export interface TrackRecordTicker {
  ticker: string
  n: number
  hitRate: number
  alpha: number
}

export interface ReliabilityPoint {
  bucket: number
  predicted: number
  observed: number
  n?: number
}

export interface TrackRecordData {
  resolved: number
  pending: number
  hitRate: number | null
  directionalAccuracy: number | null
  meanPredP50: number | null
  meanRealized: number | null
  alphaMean: number | null
  alphaHitRate: number | null
  byTicker: TrackRecordTicker[]
  reliability: ReliabilityPoint[]
  source?: string
}

export interface HeaderInfo {
  kicker: string
  title: string
  subtitle: string
}

export type ViewId = 'overview' | 'trackrecord' | 'portfolio' | 'journal' | 'calibration' | 'validation'

// ---------- header copy per view ----------

export const headers: Record<ViewId, HeaderInfo> = {
  overview: {
    kicker: 'Single-trader market intelligence',
    title: 'Overview',
    subtitle:
      'What is, and is not, statistically supported right now — every claim carries its error bars and its validation status.',
  },
  trackrecord: {
    kicker: 'Self-grading',
    title: 'Track record',
    subtitle:
      "The system grading its own past calls, resolved against realised forward returns — distinct from Calibration, which grades the trader.",
  },
  portfolio: { kicker: 'Layer 6', title: 'Portfolio diagnostics', subtitle: 'Current weights, factor stress scenarios and correlation clusters.' },
  journal: { kicker: 'Layer 8', title: 'Trader journal', subtitle: 'Log theses with what would invalidate them; review open and completed trades.' },
  calibration: { kicker: 'Layer 9', title: 'Calibration', subtitle: 'Are your confidence levels honest? Reliability vs observed outcomes, Brier and ECE.' },
  validation: {
    kicker: 'Layer 0',
    title: 'Validation gate',
    subtitle: 'The five sign-off criteria for every layer. Nothing upstream is treated as evidence until it passes here.',
  },
}

// ---------- navigation ----------

export interface NavItem {
  id: ViewId | 'query'
  label: string
  tag?: string
  disabled?: boolean
  title?: string
}

export const navItems: NavItem[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'trackrecord', label: 'Track record' },
  { id: 'portfolio', label: 'Portfolio' },
  { id: 'journal', label: 'Journal' },
  { id: 'calibration', label: 'Calibration' },
  { id: 'validation', label: 'Validation' },
  { id: 'query', label: 'Query (LLM)', tag: 'OFF', disabled: true, title: 'Enable LLM_ENABLED in .env to use this page' },
]
