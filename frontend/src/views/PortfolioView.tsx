import { colors, fonts } from '../theme'
import { card, sectionLabel, microLabel, redBanner } from '../styles'
import type { PortfolioData } from '../api'

export default function PortfolioView({
  portfolio,
  scenario,
  onScenario,
}: {
  portfolio: PortfolioData
  scenario: string
  onScenario: (s: string) => void
}) {
  const maxW = Math.max(...portfolio.weights.map((x) => x.w))
  const sdata = portfolio.stressMap[scenario]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1.3fr 1fr', gap: 18 }}>
        {/* current weights */}
        <section style={card}>
          <h2 style={{ ...sectionLabel, margin: '0 0 16px' }}>Layer 6 — Current weights</h2>
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 1,
              background: colors.borderMid,
              border: `1px solid ${colors.borderMid}`,
              borderRadius: 8,
              overflow: 'hidden',
            }}
          >
            {portfolio.weights.map((w) => (
              <div
                key={w.ticker}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '90px 1fr 64px',
                  gap: 14,
                  alignItems: 'center',
                  padding: '11px 14px',
                  background: colors.cardInner,
                }}
              >
                <span style={{ font: `600 13px/1 ${fonts.mono}`, color: colors.text }}>{w.ticker}</span>
                <div style={{ height: 7, borderRadius: 4, background: colors.track, overflow: 'hidden' }}>
                  <div
                    style={{
                      height: '100%',
                      width: `${((w.w / maxW) * 100).toFixed(1)}%`,
                      borderRadius: 4,
                      background: w.ticker === 'Cash' ? colors.dim : colors.blue,
                    }}
                  />
                </div>
                <span style={{ textAlign: 'right', font: `500 13px/1 ${fonts.mono}`, color: colors.text2 }}>
                  {(w.w * 100).toFixed(0)}%
                </span>
              </div>
            ))}
          </div>
          <div
            style={{
              marginTop: 14,
              display: 'flex',
              justifyContent: 'space-between',
              font: `500 12px/1 ${fonts.mono}`,
              color: colors.text3,
            }}
          >
            <span>Portfolio effective N</span>
            <span style={{ color: colors.text2 }}>{portfolio.effectiveN}</span>
          </div>
        </section>

        {/* stress test */}
        <section style={{ ...card, display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
            <h2 style={sectionLabel}>Stress test</h2>
            <select
              value={scenario}
              onChange={(e) => onScenario(e.target.value)}
              style={{
                background: colors.cardInner,
                color: colors.text2,
                border: `1px solid ${colors.border}`,
                borderRadius: 7,
                padding: '7px 10px',
                font: `500 12px/1 ${fonts.mono}`,
                outline: 'none',
                cursor: 'pointer',
              }}
            >
              {portfolio.scenarios.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
          <div style={{ textAlign: 'center', margin: '10px 0 18px' }}>
            <div style={microLabel}>Stressed annualised vol</div>
            <div style={{ marginTop: 8, font: `600 38px/1 ${fonts.mono}`, color: colors.red }}>
              {(sdata.vol * 100).toFixed(0)}%
            </div>
            <div style={{ marginTop: 5, font: `400 11px/1 ${fonts.mono}`, color: colors.muted }}>
              baseline {(sdata.base * 100).toFixed(0)}%
            </div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {sdata.factors.map(([name, impact]) => (
              <div
                key={name}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  font: `400 12px/1 ${fonts.sans}`,
                  color: colors.text3,
                }}
              >
                <span>{name}</span>
                <span style={{ fontFamily: fonts.mono, color: colors.redText }}>{impact}</span>
              </div>
            ))}
          </div>
          <p style={{ margin: '16px 0 0', font: `400 11px/1.5 ${fonts.sans}`, color: colors.muted2 }}>
            {portfolio.stressNote}
          </p>
        </section>
      </div>

      {/* correlation cluster */}
      <section
        style={{
          ...redBanner,
          padding: '14px 18px',
          borderRadius: 10,
          display: 'flex',
          alignItems: 'center',
          gap: 12,
        }}
      >
        <span style={{ color: colors.red, fontSize: 13 }}>●</span>
        <div>
          <div style={{ font: `600 13px/1.3 ${fonts.sans}`, color: colors.text }}>
            Correlation cluster detected — {portfolio.cluster.members}
          </div>
          <div style={{ marginTop: 3, font: `400 12px/1.4 ${fonts.sans}`, color: colors.redText }}>
            These positions behave as a single trade.
          </div>
        </div>
      </section>
    </div>
  )
}
