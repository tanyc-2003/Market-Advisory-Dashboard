/**
 * Domain data for the dashboard.
 *
 * This is ported verbatim from the Claude Design mock (`Market Advisory.dc.html`).
 * It is intentionally isolated in one module so that, when the React UI is later
 * wired to the Python layer services (DuckDB), only this file's exported getters
 * need to be swapped for `fetch()` calls — the views consume typed shapes, not a
 * data source. See `src/advisory/dashboard/services.py` for the eventual backend.
 */
import type { LayerStatus } from './theme'

// ---------- types ----------

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

// ---------- snapshot ----------

export const asOf = 'Jun 27, 2026'

// ---------- layers (Layer 0 validation gate) ----------

export const layers: Layer[] = [
  { id: 'L0', name: 'Validation', status: 'production', sharpe: null, ece: null, p30: null, dsr: 0.97, rationale: 'All five sign-off criteria pass.' },
  { id: 'L1', name: 'Market State', status: 'production', sharpe: 0.71, ece: 0.041, p30: 0.18, dsr: 0.96, rationale: 'HMM passes walk-forward, calibration and deflated-Sharpe floors.' },
  { id: 'L2', name: 'Analogs', status: 'research_preview', sharpe: 0.58, ece: 0.044, p30: 0.05, dsr: 0.81, rationale: 'Deflated Sharpe 0.81 < 0.95 floor — predictive edge not yet distinguishable from trial count.' },
  { id: 'L3', name: 'Attribution', status: 'research_preview', sharpe: 0.55, ece: 0.071, p30: 0.07, dsr: 0.95, rationale: 'ECE 0.071 > 0.05 ceiling — SHAP-driven probabilities slightly overconfident.' },
  { id: 'L4', name: 'Risk Model', status: 'production', sharpe: 0.63, ece: 0.038, p30: 0.11, dsr: 0.96, rationale: 'Factor exposures and tail betas validated.' },
  { id: 'L5', name: 'Stress Monitor', status: 'production', sharpe: null, ece: null, p30: null, dsr: null, rationale: 'Friction z-scores; calendar suppression active. No predictive gate required.' },
  { id: 'L6', name: 'Portfolio', status: 'research_preview', sharpe: 0.52, ece: 0.043, p30: -0.04, dsr: 0.95, rationale: 'CPCV 30th-percentile Sharpe -0.04 < 0.0 floor — harsh-path performance is negative.' },
  { id: 'L7', name: 'Hygiene', status: 'production', sharpe: 0.66, ece: 0.039, p30: 0.09, dsr: 0.96, rationale: 'Contradiction tests pass Fisher exact + FDR-BY correction.' },
  { id: 'L8', name: 'Journal', status: 'production', sharpe: null, ece: null, p30: null, dsr: null, rationale: 'Data layer — trade record store. No predictive gate.' },
  { id: 'L9', name: 'Calibration', status: 'research_preview', sharpe: null, ece: 0.061, p30: null, dsr: null, rationale: 'ECE 0.061 > 0.05 and only 21 graded entries — near the 15-entry minimum.' },
  { id: 'L10', name: 'Sizing', status: 'research_preview', sharpe: 0.58, ece: 0.044, p30: 0.05, dsr: 0.81, rationale: 'Inherits research-preview status from Layer 2 analog returns.' },
]

// ---------- market state (Layer 1) ----------

export const states: MarketStateRow[] = [
  { name: 'Calm Bull', prob: 0.57 },
  { name: 'Volatile Bull', prob: 0.22 },
  { name: 'Neutral / transition', prob: 0.12 },
  { name: 'Calm Bear', prob: 0.06 },
  { name: 'Stressed Bear', prob: 0.03 },
]

export const marketStateMeta = {
  uncertainty: '0.41',
  transition:
    'Elevated probability of transition into Volatile Bull (0.22). Term-structure and realized-vol channels are the main contributors; treat regime persistence as the base case, not a certainty.',
}

// ---------- watchlist assets (Layers 2 · 3 · 7) ----------

export const assets: Asset[] = [
  {
    ticker: 'NVDA', sector: 'Semiconductors', n: 34, hitRate: 0.62, conf: 'moderate',
    p5: -0.084, p25: -0.021, p50: 0.018, p75: 0.057, p95: 0.121, disagreement: false,
    drivers: ['realized_vol_21d ↑', 'ret_63d ↑', 'rsi_14 ↑'],
    sizing: { raw: 0.34, std: 0.17, regime: 0.11, displayed: 0.11 },
  },
  {
    ticker: 'MSFT', sector: 'Software', n: 41, hitRate: 0.58, conf: 'moderate',
    p5: -0.061, p25: -0.012, p50: 0.014, p75: 0.041, p95: 0.083, disagreement: false,
    drivers: ['ret_21d ↑', 'pct_above_ma50 ↑', 'realized_vol_21d ↓'],
    sizing: { raw: 0.22, std: 0.13, regime: 0.09, displayed: 0.09 },
  },
  {
    ticker: 'XOM', sector: 'Energy', n: 19, hitRate: 0.53, conf: 'weak',
    p5: -0.093, p25: -0.031, p50: 0.004, p75: 0.043, p95: 0.108, disagreement: true,
    disagreementNote:
      'Global vs within-state analogs overlap only 41% — regime conditioning materially changes the picture.',
    drivers: ['ret_5d ↓', 'realized_vol_21d ↑', 'rsi_14 ↓'],
    sizing: { raw: 0.09, std: 0.06, regime: 0.04, displayed: 0.04 },
  },
  {
    ticker: 'JPM', sector: 'Financials', n: 28, hitRate: 0.6, conf: 'moderate',
    p5: -0.058, p25: -0.014, p50: 0.012, p75: 0.038, p95: 0.079, disagreement: false,
    drivers: ['ret_63d ↑', 'pct_above_ma50 ↑', 'ret_1d ↑'],
    sizing: { raw: 0.18, std: 0.11, regime: 0.08, displayed: 0.08 },
  },
  {
    ticker: 'TSLA', sector: 'Auto', n: 12, hitRate: 0.5, conf: 'insufficient',
    p5: -0.142, p25: -0.048, p50: -0.002, p75: 0.061, p95: 0.171, disagreement: true,
    disagreementNote:
      'Only 12 effective analogs and 38% overlap — distribution is too wide to read as evidence.',
    drivers: ['realized_vol_21d ↑', 'ret_5d ↓', 'rsi_14 ↓'],
    sizing: { raw: 0.04, std: 0.03, regime: 0.02, displayed: 0.02 },
  },
]

export const KELLY_CAP = '0.20'

export const sizingNote =
  'Tail-aware Kelly using 5th-percentile expected shortfall as the loss term, haircut for state uncertainty and analog disagreement, then hard-capped at 20%. A diagnostic — not a recommendation.'

// ---------- alerts + unknowns (Layer 7) ----------

export const alerts: Alert[] = [
  { sev: 3, title: 'Validated contradiction — momentum vs term structure', detail: 'Bullish 63-day momentum co-occurs with an inverted yield-curve slope. Fisher exact p < 0.01, survives FDR-BY.' },
  { sev: 2, title: 'Factor redundancy across watchlist', detail: 'The market factor explains ≥ 50% of attribution for 4 of 5 names — positions are less diversified than they appear.' },
  { sev: 1, title: 'Calendar event ahead', detail: 'FOMC day inside the 10-day horizon. Friction monitor suppresses intraday alerts on the event day itself.' },
]

export const unknowns: string[] = [
  'Forward returns are conditional on regime persistence. A regime break invalidates the analog set without warning.',
  'Two watchlist names have fewer than 20 effective analogs — their distributions are shown but should not be read as evidence.',
  'Attribution is correlational. SHAP values explain the model, not the market.',
  'The system cannot detect structural change until after it has happened.',
]

// ---------- portfolio (Layer 6) ----------

export const portfolioWeights: Weight[] = [
  { ticker: 'NVDA', w: 0.18 },
  { ticker: 'MSFT', w: 0.15 },
  { ticker: 'JPM', w: 0.12 },
  { ticker: 'XOM', w: 0.1 },
  { ticker: 'AMD', w: 0.09 },
  { ticker: 'Cash', w: 0.36 },
]

export const portfolioEffectiveN = '3.4'

export const stressScenarios: string[] = [
  '2008 Credit Crisis',
  '2011 EU Debt',
  '2020 COVID Crash',
  '2022 Rate Shock',
]

export const stressMap: Record<string, StressData> = {
  '2008 Credit Crisis': { vol: 0.41, base: 0.17, factors: [['Equity beta', '-31.2%'], ['Credit (HY) spread', '-14.8%'], ['Volatility', '+22.0%']] },
  '2011 EU Debt': { vol: 0.33, base: 0.17, factors: [['Equity beta', '-19.4%'], ['Rates (TLT)', '+6.1%'], ['Volatility', '+15.5%']] },
  '2020 COVID Crash': { vol: 0.48, base: 0.17, factors: [['Equity beta', '-34.0%'], ['Volatility', '+28.3%'], ['Commodity', '-12.6%']] },
  '2022 Rate Shock': { vol: 0.29, base: 0.17, factors: [['Rates (TLT)', '-17.9%'], ['Growth / QQQ', '-21.4%'], ['USD (UUP)', '+5.2%']] },
}

export const stressNote =
  'Shocks applied to fitted factor betas under a two-regime covariance (MCD with Ledoit-Wolf fallback). Historical analogy, not a forecast.'

export const correlationCluster = { members: 'NVDA + AMD' }

// ---------- journal (Layer 8) ----------

export const journalOpen: OpenTrade[] = [
  { ticker: 'NVDA', direction: 'long', conf: 4, thesis: 'Calm-bull regime + strong 63d momentum; invalidates on vol regime break.', opened: 'Jun 18' },
  { ticker: 'XOM', direction: 'short', conf: 2, thesis: 'Weak analogs, low conviction; sized small. Invalidates above MA50.', opened: 'Jun 23' },
  { ticker: 'JPM', direction: 'long', conf: 3, thesis: 'Financials breadth improving; cut if curve re-inverts hard.', opened: 'Jun 25' },
]

export const journalClosed: ClosedTrade[] = [
  { ticker: 'MSFT', direction: 'long', outcome: 'Thesis confirmed — held 12d', pnl: '+4.2%' },
  { ticker: 'TSLA', direction: 'long', outcome: 'Invalidated — vol spike, cut early', pnl: '-3.1%' },
  { ticker: 'AAPL', direction: 'avoided', outcome: 'Sat out — insufficient analogs', pnl: '—' },
]

// ---------- calibration (Layer 9) ----------

export const calRows: CalRow[] = [
  { band: '1', implied: 0.3, observed: 0.34, lo: 0.1, hi: 0.62, n: 3 },
  { band: '2', implied: 0.45, observed: 0.4, lo: 0.18, hi: 0.67, n: 4 },
  { band: '3', implied: 0.55, observed: 0.5, lo: 0.27, hi: 0.73, n: 6 },
  { band: '4', implied: 0.7, observed: 0.6, lo: 0.31, hi: 0.83, n: 5 },
  { band: '5', implied: 0.85, observed: 0.67, lo: 0.3, hi: 0.9, n: 3 },
]

export const calibrationCards = [
  { label: 'Brier score', value: '0.214', note: 'Lower is better. 0.25 = coin flip.' },
  { label: 'Expected calibration error', value: '0.061', note: 'Above the 0.05 ceiling — mild overconfidence.' },
  { label: 'Graded entries', value: '21', note: 'Above the 15-entry minimum, below comfort.' },
]

export const calibrationDrift =
  '4 invalidated-and-lost trades in the last 30 days exceeds the threshold of 3 — high-confidence calls are not surviving contact with the market.'

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

export const gateCounts = {
  production: layers.filter((l) => l.status === 'production').length,
  preview: layers.filter((l) => l.status === 'research_preview').length,
}
