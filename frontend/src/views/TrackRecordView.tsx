import { colors, fonts, fmtPct } from '../theme'
import { card, cardFlush, sectionLabel } from '../styles'
import type { TrackRecordData } from '../data'

interface Props {
  trackRecord: TrackRecordData
}

function pct1(v: number | null | undefined): string {
  return v === null || v === undefined ? '—' : (v * 100).toFixed(1) + '%'
}

export default function TrackRecordView({ trackRecord: tr }: Props) {
  const cards = [
    { label: 'Resolved (+ pending)', value: `${tr.resolved} / ${tr.pending}`, color: colors.text, note: 'Calls resolved against realised forward return.' },
    {
      label: 'Hit rate',
      value: pct1(tr.hitRate),
      color: (tr.hitRate ?? 0) >= 0.5 ? colors.green : colors.red,
      note: `Directional accuracy: ${pct1(tr.directionalAccuracy)}`,
    },
    {
      label: 'Mean pred. vs realised',
      value: `${fmtPct(tr.meanPredP50, true)} / ${fmtPct(tr.meanRealized, true)}`,
      color: colors.text2,
      note: 'Predicted p50 vs realised forward return.',
    },
    {
      label: 'Mean alpha vs SPY',
      value: fmtPct(tr.alphaMean, true),
      color: (tr.alphaMean ?? 0) >= 0 ? colors.green : colors.red,
      note: `Alpha hit-rate ${pct1(tr.alphaHitRate)}`,
    },
  ]

  const trCx = (p: number) => (p * 230).toFixed(1)
  const trCy = (p: number) => (230 - p * 230).toFixed(1)
  const points = tr.reliability.map((r) => ({ cx: trCx(r.predicted), cy: trCy(r.observed) }))
  const polyline = tr.reliability.map((r) => `${trCx(r.predicted)},${trCy(r.observed)}`).join(' ')

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 14 }}>
        {cards.map((c, i) => (
          <div key={i} style={{ ...card, padding: '20px 22px' }}>
            <div style={{ font: `500 10px/1 ${fonts.mono}`, color: colors.muted, textTransform: 'uppercase', letterSpacing: '0.08em' }}>{c.label}</div>
            <div style={{ marginTop: 10, font: `600 28px/1 ${fonts.mono}`, color: c.color }}>{c.value}</div>
            <div style={{ marginTop: 7, font: `400 11px/1.4 ${fonts.sans}`, color: colors.muted2 }}>{c.note}</div>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '300px 1fr', gap: 18, alignItems: 'start' }}>
        <section style={card}>
          <h2 style={{ ...sectionLabel, margin: '0 0 18px' }}>Reliability — system's own calls</h2>
          <div style={{ position: 'relative', width: 230, height: 230, margin: '0 auto', background: colors.cardInner, border: `1px solid ${colors.borderMid}`, borderRadius: 8 }}>
            <svg viewBox="0 0 230 230" width="230" height="230" style={{ position: 'absolute', inset: 0 }}>
              <line x1="0" y1="230" x2="230" y2="0" stroke={colors.dim} strokeWidth="1" strokeDasharray="4 4" />
              <polyline points={polyline} fill="none" stroke={colors.blue} strokeWidth="2" />
              {points.map((p, i) => (
                <circle key={i} cx={p.cx} cy={p.cy} r="4.5" fill={colors.blue} stroke={colors.card} strokeWidth="2" />
              ))}
            </svg>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8, font: `400 10px/1 ${fonts.mono}`, color: colors.muted }}>
            <span>0% predicted</span>
            <span>perfect = diagonal</span>
            <span>100%</span>
          </div>
        </section>

        <section style={cardFlush}>
          <div style={{ display: 'grid', gridTemplateColumns: '80px 60px 90px 90px', gap: 14, padding: '12px 22px', borderBottom: `1px solid ${colors.borderMid}`, font: `500 10px/1 ${fonts.mono}`, color: colors.muted, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            <span>Ticker</span>
            <span style={{ textAlign: 'right' }}>N</span>
            <span style={{ textAlign: 'right' }}>Hit rate</span>
            <span style={{ textAlign: 'right' }}>Alpha</span>
          </div>
          {tr.byTicker.map((r, i) => (
            <div key={i} style={{ display: 'grid', gridTemplateColumns: '80px 60px 90px 90px', gap: 14, padding: '13px 22px', borderBottom: `1px solid ${colors.borderSoft}`, alignItems: 'center' }}>
              <span style={{ font: `600 13px/1 ${fonts.mono}`, color: colors.text }}>{r.ticker}</span>
              <span style={{ textAlign: 'right', font: `500 12px/1 ${fonts.mono}`, color: colors.text3 }}>{r.n}</span>
              <span style={{ textAlign: 'right', font: `500 12px/1 ${fonts.mono}`, color: colors.text2 }}>{(r.hitRate * 100).toFixed(0)}%</span>
              <span style={{ textAlign: 'right', font: `500 12px/1 ${fonts.mono}`, color: r.alpha >= 0 ? colors.green : colors.red }}>{fmtPct(r.alpha, true)}</span>
            </div>
          ))}
          <div style={{ margin: '16px 22px', padding: '13px 15px', borderRadius: 8, background: 'rgba(122,162,247,0.08)', border: '1px solid rgba(122,162,247,0.24)', font: `400 11px/1.5 ${fonts.sans}`, color: colors.text3 }}>
            The system grading its own past calls — distinct from Calibration, which grades the trader. Numbers are shown as-is, including when unflattering.
          </div>
        </section>
      </div>
    </div>
  )
}
