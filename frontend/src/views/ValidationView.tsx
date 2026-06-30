import type { CSSProperties } from 'react'
import { colors, fonts, statusColor, statusText, num } from '../theme'
import { card, cardFlush } from '../styles'
import type { Layer } from '../data'
import type { ValidationSummary } from '../api'

const cols = '48px 1fr 130px 110px 100px 100px'

/** Colour a metric cell: dim when N/A, neutral when it passes its floor,
 *  amber when it fails — mirroring the design's `fail()` helper. */
function metricStyle(value: number | null, ok: boolean): CSSProperties {
  const color = value === null ? colors.dimText : ok ? colors.text2 : colors.amber
  return { textAlign: 'right', font: `500 13px/1 ${fonts.mono}`, color }
}

function StatusPill({ status }: { status: Layer['status'] }) {
  const col = statusColor(status)
  return (
    <span
      style={{
        font: `500 9px/1 ${fonts.mono}`,
        letterSpacing: '0.05em',
        textTransform: 'uppercase',
        padding: '3px 6px',
        borderRadius: 4,
        color: col,
        background: `${col}1a`,
        border: `1px solid ${col}44`,
      }}
    >
      {statusText(status)}
    </span>
  )
}

function SummaryCard({ label, value, valueColor, note }: { label: string; value: string; valueColor: string; note: string }) {
  return (
    <div style={{ flex: 1, ...card, padding: '20px 22px' }}>
      <div style={{ font: `500 10px/1 ${fonts.mono}`, color: colors.muted, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
        {label}
      </div>
      <div style={{ marginTop: 10, font: `600 28px/1 ${fonts.mono}`, color: valueColor }}>{value}</div>
      <div style={{ marginTop: 6, font: `400 11px/1.4 ${fonts.sans}`, color: colors.muted2 }}>{note}</div>
    </div>
  )
}

export default function ValidationView({
  layers,
  validation,
}: {
  layers: Layer[]
  validation: ValidationSummary
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      <section style={cardFlush}>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: cols,
            gap: 14,
            padding: '12px 22px',
            borderBottom: `1px solid ${colors.borderMid}`,
            font: `500 10px/1 ${fonts.mono}`,
            color: colors.muted,
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
          }}
        >
          <span>Layer</span>
          <span>Status / rationale</span>
          <span style={{ textAlign: 'right' }}>WF Sharpe</span>
          <span style={{ textAlign: 'right' }}>ECE</span>
          <span style={{ textAlign: 'right' }}>CPCV p30</span>
          <span style={{ textAlign: 'right' }}>DSR</span>
        </div>

        {layers.map((L) => (
          <div
            key={L.id}
            style={{
              display: 'grid',
              gridTemplateColumns: cols,
              gap: 14,
              padding: '14px 22px',
              borderBottom: `1px solid ${colors.borderSoft}`,
              alignItems: 'center',
            }}
          >
            <span style={{ font: `600 12px/1 ${fonts.mono}`, color: colors.text2 }}>{L.id}</span>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', flex: 'none', background: statusColor(L.status) }} />
                <span style={{ font: `500 13px/1 ${fonts.sans}`, color: colors.text }}>{L.name}</span>
                <StatusPill status={L.status} />
              </div>
              <div style={{ marginTop: 5, marginLeft: 17, font: `400 11px/1.4 ${fonts.sans}`, color: colors.muted3 }}>
                {L.rationale}
              </div>
            </div>
            <span style={metricStyle(L.sharpe, L.sharpe !== null && L.sharpe >= 0.5)}>{num(L.sharpe)}</span>
            <span style={metricStyle(L.ece, L.ece !== null && L.ece <= 0.05)}>{num(L.ece)}</span>
            <span style={metricStyle(L.p30, L.p30 !== null && L.p30 >= 0)}>{num(L.p30)}</span>
            <span style={metricStyle(L.dsr, L.dsr !== null && L.dsr >= 0.95)}>{num(L.dsr)}</span>
          </div>
        ))}
      </section>

      <div style={{ display: 'flex', gap: 18 }}>
        <SummaryCard
          label="Survivorship coverage"
          value={validation.survivorshipCoverage}
          valueColor={colors.green}
          note="Above 0.95 target. Delisted-ticker representation is plausible."
        />
        <SummaryCard
          label="DSR trials in audit log"
          value={validation.dsrTrials}
          valueColor={colors.text2}
          note="Deflated Sharpe floors at max(logged, 2000). We cannot pretend fewer trials."
        />
      </div>
    </div>
  )
}
