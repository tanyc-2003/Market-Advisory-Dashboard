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
