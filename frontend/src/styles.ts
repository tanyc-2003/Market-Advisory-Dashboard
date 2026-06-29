import type { CSSProperties } from 'react'
import { colors, fonts } from './theme'

/** Shared, typed style fragments used across views. Annotating them as
 *  CSSProperties keeps string-literal unions (e.g. textTransform) type-checked. */

export const card: CSSProperties = {
  background: colors.card,
  border: `1px solid ${colors.border}`,
  borderRadius: 12,
  padding: '22px 24px',
}

export const cardFlush: CSSProperties = {
  background: colors.card,
  border: `1px solid ${colors.border}`,
  borderRadius: 12,
  overflow: 'hidden',
}

/** mono, uppercase, tracked section heading (h2) */
export const sectionLabel: CSSProperties = {
  margin: 0,
  font: `600 11px/1 ${fonts.mono}`,
  letterSpacing: '0.12em',
  textTransform: 'uppercase',
  color: colors.muted,
}

/** small mono uppercase caption */
export const microLabel: CSSProperties = {
  font: `500 10px/1 ${fonts.mono}`,
  color: colors.muted,
  textTransform: 'uppercase',
  letterSpacing: '0.08em',
}

/** amber "research preview" inline banner */
export const amberBanner: CSSProperties = {
  borderRadius: 7,
  background: 'rgba(224,176,74,0.09)',
  border: '1px solid rgba(224,176,74,0.28)',
}

/** red "danger" inline banner */
export const redBanner: CSSProperties = {
  borderRadius: 8,
  background: 'rgba(224,108,108,0.08)',
  border: '1px solid rgba(224,108,108,0.26)',
}
