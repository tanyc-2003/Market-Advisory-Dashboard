/**
 * Shared types + static UI copy for the dashboard.
 *
 * Domain *values* (layers, market state, watchlist, sizing, portfolio, journal,
 * calibration, validation summaries) are no longer defined here — they are
 * fetched from the API (see `src/api.ts`, backed by `src/advisory/api/`). This
 * module now holds only the TypeScript shapes those payloads conform to, plus
 * client-side UI concerns (navigation, per-view header copy).
 */
import type { LayerStatus } from './theme'

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

export interface HeaderInfo {
  kicker: string
  title: string
  subtitle: string
}

export type ViewId = 'overview' | 'portfolio' | 'journal' | 'calibration' | 'validation'

// ---------- header copy per view ----------

export const headers: Record<ViewId, HeaderInfo> = {
  overview: {
    kicker: 'Single-trader market intelligence',
    title: 'Overview',
    subtitle:
      'What is, and is not, statistically supported right now — every claim carries its error bars and its validation status.',
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
  { id: 'portfolio', label: 'Portfolio' },
  { id: 'journal', label: 'Journal' },
  { id: 'calibration', label: 'Calibration' },
  { id: 'validation', label: 'Validation' },
  { id: 'query', label: 'Query (LLM)', tag: 'OFF', disabled: true, title: 'Enable LLM_ENABLED in .env to use this page' },
]
