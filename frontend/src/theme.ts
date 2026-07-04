/**
 * Design tokens + formatting helpers, ported verbatim from the Claude Design
 * source (`Market Advisory.dc.html`). Colours, fonts and the numeric helpers
 * here are the single source of truth for the visual language so the rest of
 * the app never hard-codes a hex value.
 */

export const colors = {
  bg: '#101319',
  sidebar: '#0c0f14',
  card: '#161a21',
  cardInner: '#12161d',
  cardInner2: '#13171e',
  selRow: '#161d2b',
  navActive: '#1b2436',
  border: '#2a2f38',
  borderSoft: '#1d222b',
  borderMid: '#242a33',
  track: '#1f242d',
  text: '#e7eaee',
  text2: '#cdd3dc',
  text3: '#9aa3b0',
  textNav: '#cdd6f4',
  muted: '#6b7480',
  muted2: '#7e8794',
  muted3: '#8a93a0',
  muted4: '#b8c0cc',
  blue: '#7aa2f7',
  blueHover: '#8fb2ff',
  blueDim: '#3a4a6b',
  blueDeep: '#4a5670',
  green: '#5fbf7f',
  amber: '#e0b04a',
  amberText: '#d8c089',
  amberText2: '#a8895a',
  red: '#e06c6c',
  redText: '#d79a9a',
  dim: '#3a414d',
  dimText: '#4a525e',
  navDisabled: '#525964',
} as const

export const fonts = {
  sans: "'IBM Plex Sans', system-ui, sans-serif",
  mono: "'IBM Plex Mono', monospace",
} as const

export type LayerStatus = 'production' | 'research_preview' | 'blocked' | 'no_report'

export function statusColor(s: LayerStatus): string {
  return {
    production: colors.green,
    research_preview: colors.amber,
    blocked: colors.red,
    no_report: colors.muted,
  }[s]
}

export function statusText(s: LayerStatus): string {
  return {
    production: 'Production',
    research_preview: 'Research preview',
    blocked: 'Blocked',
    no_report: 'No report',
  }[s]
}

/** Format a fraction as a percentage string; optionally prefix a "+" for positives. */
export function fmtPct(v: number | null | undefined, signed = false): string {
  if (v === null || v === undefined) return '—'
  const s = (v * 100).toFixed(1) + '%'
  return signed && v > 0 ? '+' + s : s
}

/** Map a return value in the [-0.16, 0.16] window onto a 0–100 track position. */
export function pos(v: number): number {
  const lo = -0.16
  const hi = 0.16
  const p = (v - lo) / (hi - lo)
  return Math.max(0, Math.min(1, p)) * 100
}

/** Two-decimal numeric formatter that renders null/undefined as an em dash. */
export function num(v: number | null | undefined): string {
  if (v === null || v === undefined) return '—'
  return v.toFixed(2)
}

/** Format a fraction as a whole-percent probability, em dash for null. */
export function fmtProb(v: number | null | undefined): string {
  return v === null || v === undefined ? '—' : (v * 100).toFixed(0) + '%'
}

/** Feed-health status → dot colour. */
export function healthDotColor(s: string): string {
  return { fresh: colors.green, stale: colors.amber, missing: colors.red }[s] ?? colors.muted
}

/** Stress level → gauge colour. */
export function stressColor(level: string): string {
  return (
    { calm: colors.green, normal: colors.blue, elevated: colors.amber, stressed: colors.red }[level] ??
    colors.blue
  )
}

/** P(up) → colour: green when confidently up, red when confidently down, neutral otherwise. */
export function pUpColor(p: number): string {
  return p >= 0.58 ? colors.green : p <= 0.45 ? colors.red : colors.text3
}

/** Bull/bear verdict → colour. */
export function verdictColor(v: string): string {
  return { 'lean long': colors.green, neutral: colors.text3, 'lean short': colors.red }[v] ?? colors.text3
}

/** Notes-inbox kind → chip colour. */
export function kindColor(k: string): string {
  return { outcome: colors.green, system: colors.blue, alert: colors.amber, user: colors.text3 }[k] ?? colors.text3
}

/** A colour + its low-alpha background/border variants, for pill styling. */
export function alphaVariants(hex: string): { fg: string; bg: string; border: string } {
  return { fg: hex, bg: hex + '1a', border: hex + '44' }
}

export interface ForecastBand {
  h: number
  p5: number
  p50: number
  p95: number
}

export interface FanGeometry {
  zeroY: string
  linePoints: string
  bandPath: string
  dots: Array<{ x: string; y: string }>
}

/**
 * Build the SVG geometry for the forecast fan (median path + p5–p95 band),
 * ported verbatim from the design source so the picture is identical.
 */
export function buildFan(forecast: ForecastBand[]): FanGeometry {
  const w = 760
  const h = 150
  const padL = 20
  const padR = 20
  const top = 14
  const bot = 30
  const innerH = h - top - bot
  const maxH = 10
  const lo = -0.16
  const hi = 0.2
  const xOf = (hVal: number) => padL + (hVal / maxH) * (w - padL - padR)
  const yOf = (v: number) => {
    let p = (v - lo) / (hi - lo)
    p = Math.max(0, Math.min(1, p))
    return top + (1 - p) * innerH
  }
  const zeroY = yOf(0)
  const dots = forecast.map((f) => ({ x: xOf(f.h).toFixed(1), y: yOf(f.p50).toFixed(1) }))
  const linePoints = forecast.map((f) => xOf(f.h).toFixed(1) + ',' + yOf(f.p50).toFixed(1)).join(' ')
  const top5 = forecast.map((f) => xOf(f.h).toFixed(1) + ',' + yOf(f.p95).toFixed(1)).join(' L ')
  const bot5 = forecast
    .slice()
    .reverse()
    .map((f) => xOf(f.h).toFixed(1) + ',' + yOf(f.p5).toFixed(1))
    .join(' L ')
  const bandPath = 'M ' + top5 + ' L ' + bot5 + ' Z'
  return { zeroY: zeroY.toFixed(1), linePoints, bandPath, dots }
}
