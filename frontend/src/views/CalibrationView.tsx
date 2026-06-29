import { colors, fonts } from '../theme'
import { card, cardFlush, sectionLabel, microLabel, amberBanner } from '../styles'
import { calRows, calibrationCards, calibrationDrift } from '../data'

const cx = (p: number) => (p * 260).toFixed(1)
const cy = (p: number) => (260 - p * 260).toFixed(1)

const rowCols = '90px 1fr 1fr 64px'

export default function CalibrationView() {
  const points = calRows.map((r) => ({ cx: cx(r.implied), cy: cy(r.observed) }))
  const polyline = calRows.map((r) => `${cx(r.implied)},${cy(r.observed)}`).join(' ')

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      {/* metric cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14 }}>
        {calibrationCards.map((c) => (
          <div key={c.label} style={{ ...card, padding: '20px 22px' }}>
            <div style={microLabel}>{c.label}</div>
            <div style={{ marginTop: 10, font: `600 30px/1 ${fonts.mono}`, color: colors.text }}>{c.value}</div>
            <div style={{ marginTop: 7, font: `400 11px/1.4 ${fonts.sans}`, color: colors.muted2 }}>{c.note}</div>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '340px 1fr', gap: 18, alignItems: 'start' }}>
        {/* reliability diagram */}
        <section style={card}>
          <h2 style={{ ...sectionLabel, margin: '0 0 18px' }}>Reliability diagram</h2>
          <div
            style={{
              position: 'relative',
              width: 260,
              height: 260,
              margin: '0 auto',
              background: colors.cardInner,
              border: `1px solid ${colors.borderMid}`,
              borderRadius: 8,
            }}
          >
            <svg viewBox="0 0 260 260" width={260} height={260} style={{ position: 'absolute', inset: 0 }}>
              <line x1="0" y1="260" x2="260" y2="0" stroke={colors.dim} strokeWidth="1" strokeDasharray="4 4" />
              <polyline points={polyline} fill="none" stroke={colors.blue} strokeWidth="2" />
              {points.map((p, i) => (
                <circle key={i} cx={p.cx} cy={p.cy} r="4.5" fill={colors.blue} stroke={colors.card} strokeWidth="2" />
              ))}
            </svg>
          </div>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              marginTop: 8,
              font: `400 10px/1 ${fonts.mono}`,
              color: colors.muted,
            }}
          >
            <span>0% predicted</span>
            <span>perfect = diagonal</span>
            <span>100%</span>
          </div>
        </section>

        {/* calibration table */}
        <section style={cardFlush}>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: rowCols,
              gap: 14,
              padding: '12px 22px',
              borderBottom: `1px solid ${colors.borderMid}`,
              font: `500 10px/1 ${fonts.mono}`,
              color: colors.muted,
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
            }}
          >
            <span>Conf.</span>
            <span>Implied</span>
            <span>Observed (95% CI)</span>
            <span style={{ textAlign: 'right' }}>N</span>
          </div>
          {calRows.map((r) => (
            <div
              key={r.band}
              style={{
                display: 'grid',
                gridTemplateColumns: rowCols,
                gap: 14,
                padding: '13px 22px',
                borderBottom: `1px solid ${colors.borderSoft}`,
                alignItems: 'center',
              }}
            >
              <span style={{ font: `500 12px/1 ${fonts.mono}`, color: colors.text2 }}>{r.band}/5</span>
              <span style={{ font: `500 12px/1 ${fonts.mono}`, color: colors.text3 }}>
                {(r.implied * 100).toFixed(0)}%
              </span>
              <span style={{ font: `500 12px/1 ${fonts.mono}`, color: colors.text }}>
                {(r.observed * 100).toFixed(0)}%{' '}
                <span style={{ color: colors.muted }}>
                  [{(r.lo * 100).toFixed(0)}–{(r.hi * 100).toFixed(0)}]
                </span>
              </span>
              <span style={{ textAlign: 'right', font: `500 12px/1 ${fonts.mono}`, color: colors.text2 }}>{r.n}</span>
            </div>
          ))}
          <div
            style={{
              ...amberBanner,
              margin: '16px 22px',
              padding: '13px 15px',
              borderRadius: 8,
              display: 'flex',
              gap: 11,
              alignItems: 'flex-start',
            }}
          >
            <span style={{ color: colors.amber, fontSize: 12 }}>▲</span>
            <div>
              <div style={{ font: `600 12px/1.3 ${fonts.sans}`, color: colors.text }}>Thesis drift detected</div>
              <div style={{ marginTop: 4, font: `400 11px/1.45 ${fonts.sans}`, color: colors.amberText }}>
                {calibrationDrift}
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}
