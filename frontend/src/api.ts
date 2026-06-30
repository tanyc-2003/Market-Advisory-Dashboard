/**
 * Typed client for the dashboard API (FastAPI, see src/advisory/api/).
 *
 * The whole dashboard loads from `GET /api/dashboard` in one round trip; the
 * journal form posts to `POST /api/journal`, which returns the refreshed
 * payload. In dev, Vite proxies `/api` to http://localhost:8000 (vite.config.ts);
 * override with VITE_API_BASE for other deployments.
 */
import type {
  Layer,
  MarketStateRow,
  Asset,
  Alert,
  Weight,
  StressData,
  OpenTrade,
  ClosedTrade,
  CalRow,
} from './data'

export interface Gate {
  production: number
  preview: number
}

export interface Meta {
  asOf: string
  appMode: string
  developerMode: boolean
  llmEnabled: boolean
  kellyCap: string
  gate: Gate
  /** true when the DuckDB main store exists (seeded/journaled); false = representative data. */
  live: boolean
}

export interface MarketState {
  states: MarketStateRow[]
  uncertainty: string
  transition: string
}

export interface PortfolioData {
  weights: Weight[]
  effectiveN: string
  scenarios: string[]
  stressMap: Record<string, StressData>
  stressNote: string
  cluster: { members: string }
}

export interface JournalData {
  open: OpenTrade[]
  closed: ClosedTrade[]
}

export interface CalibrationCard {
  label: string
  value: string
  note: string
}

export interface CalibrationData {
  cards: CalibrationCard[]
  rows: CalRow[]
  drift: string
}

export interface ValidationSummary {
  survivorshipCoverage: string
  dsrTrials: string
}

export interface DashboardData {
  meta: Meta
  layers: Layer[]
  marketState: MarketState
  assets: Asset[]
  alerts: Alert[]
  unknowns: string[]
  sizingNote: string
  portfolio: PortfolioData
  journal: JournalData
  calibration: CalibrationData
  validation: ValidationSummary
}

export interface JournalEntryInput {
  ticker: string
  direction: string
  confidence: number
  thesis: string
}

export interface JournalCloseInput {
  /** Realised P&L as a percentage, e.g. -3.1 for -3.1%. */
  pnlPct: number
  exitReason: string
  thesisValidated: boolean
}

export type JournalSubmitResult = { ok: true } | { ok: false; error: string }

const BASE: string = import.meta.env.VITE_API_BASE ?? '/api'

export async function fetchDashboard(signal?: AbortSignal): Promise<DashboardData> {
  const res = await fetch(`${BASE}/dashboard`, { signal })
  if (!res.ok) throw new Error(`Dashboard request failed (${res.status})`)
  return (await res.json()) as DashboardData
}

async function errorDetail(res: Response, fallback: string): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: unknown }
    if (body?.detail) return typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
  } catch {
    /* non-JSON error body — keep the status message */
  }
  return fallback
}

export async function postJournalEntry(entry: JournalEntryInput): Promise<DashboardData> {
  const res = await fetch(`${BASE}/journal`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(entry),
  })
  if (!res.ok) throw new Error(await errorDetail(res, `Journal request failed (${res.status})`))
  return (await res.json()) as DashboardData
}

export async function closeJournalEntry(id: string, payload: JournalCloseInput): Promise<DashboardData> {
  const res = await fetch(`${BASE}/journal/${encodeURIComponent(id)}/close`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(await errorDetail(res, `Close request failed (${res.status})`))
  return (await res.json()) as DashboardData
}
