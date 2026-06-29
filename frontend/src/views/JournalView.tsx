import { useState, type CSSProperties } from 'react'
import { colors, fonts } from '../theme'
import { cardFlush, card } from '../styles'
import { journalOpen, journalClosed } from '../data'

function dirStyle(d: string): CSSProperties {
  const color = d === 'long' ? colors.green : d === 'short' ? colors.red : colors.text3
  return {
    font: `500 11px/1 ${fonts.mono}`,
    letterSpacing: '0.04em',
    textTransform: 'uppercase',
    color,
  }
}

function pnlColor(pnl: string): string {
  if (pnl.startsWith('+')) return colors.green
  if (pnl.startsWith('-')) return colors.red
  return colors.muted
}

const sectionHead: CSSProperties = {
  padding: '16px 22px',
  borderBottom: `1px solid ${colors.borderMid}`,
  font: `600 11px/1 ${fonts.mono}`,
  letterSpacing: '0.12em',
  textTransform: 'uppercase',
  color: colors.muted,
}

const fieldLabel: CSSProperties = {
  font: `500 11px/1 ${fonts.sans}`,
  color: colors.text3,
  display: 'block',
  marginBottom: 6,
}

const inputStyle: CSSProperties = {
  width: '100%',
  background: colors.cardInner,
  color: colors.text,
  border: `1px solid ${colors.border}`,
  borderRadius: 7,
  padding: '9px 11px',
  font: `500 13px/1 ${fonts.mono}`,
  outline: 'none',
}

function NewEntryForm() {
  const [hover, setHover] = useState(false)
  return (
    <section style={{ ...card, padding: '22px 22px', position: 'sticky', top: 104 }}>
      <h2 style={{ margin: '0 0 16px', font: `600 11px/1 ${fonts.mono}`, letterSpacing: '0.12em', textTransform: 'uppercase', color: colors.muted }}>
        New entry
      </h2>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 13 }}>
        <div>
          <label style={fieldLabel}>Ticker</label>
          <input placeholder="e.g. NVDA" style={inputStyle} />
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <div style={{ flex: 1 }}>
            <label style={fieldLabel}>Direction</label>
            <select style={{ ...inputStyle, cursor: 'pointer' }} defaultValue="long">
              <option value="long">long</option>
              <option value="short">short</option>
              <option value="avoided">avoided</option>
            </select>
          </div>
          <div style={{ width: 96 }}>
            <label style={fieldLabel}>Conf. 1–5</label>
            <input defaultValue="3" style={inputStyle} />
          </div>
        </div>
        <div>
          <label style={fieldLabel}>Thesis</label>
          <textarea
            rows={3}
            placeholder="What is the bet, and what would invalidate it?"
            style={{
              ...inputStyle,
              font: `400 12px/1.5 ${fonts.sans}`,
              resize: 'vertical',
            }}
          />
        </div>
        <button
          onMouseEnter={() => setHover(true)}
          onMouseLeave={() => setHover(false)}
          style={{
            marginTop: 4,
            background: hover ? colors.blueHover : colors.blue,
            color: colors.sidebar,
            border: 'none',
            borderRadius: 8,
            padding: 11,
            font: `600 13px/1 ${fonts.sans}`,
            cursor: 'pointer',
            transition: 'background .12s',
          }}
        >
          Log entry
        </button>
      </div>
    </section>
  )
}

export default function JournalView() {
  const openCols = '80px 80px 70px 1fr 90px'
  const closedCols = '80px 80px 1fr 90px'

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 18, alignItems: 'start' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
        {/* open trades */}
        <section style={cardFlush}>
          <div style={sectionHead}>Open trades</div>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: openCols,
              gap: 14,
              padding: '10px 22px',
              borderBottom: `1px solid ${colors.borderMid}`,
              font: `500 10px/1 ${fonts.mono}`,
              color: colors.muted,
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
            }}
          >
            <span>Ticker</span>
            <span>Direction</span>
            <span>Conf.</span>
            <span>Thesis</span>
            <span style={{ textAlign: 'right' }}>Opened</span>
          </div>
          {journalOpen.map((t) => (
            <div
              key={t.ticker}
              style={{
                display: 'grid',
                gridTemplateColumns: openCols,
                gap: 14,
                padding: '13px 22px',
                borderBottom: `1px solid ${colors.borderSoft}`,
                alignItems: 'center',
              }}
            >
              <span style={{ font: `600 13px/1 ${fonts.mono}`, color: colors.text }}>{t.ticker}</span>
              <span style={dirStyle(t.direction)}>{t.direction}</span>
              <span style={{ font: `500 12px/1 ${fonts.mono}`, color: colors.text2 }}>{t.conf}/5</span>
              <span style={{ font: `400 12px/1.4 ${fonts.sans}`, color: colors.text3 }}>{t.thesis}</span>
              <span style={{ textAlign: 'right', font: `400 11px/1 ${fonts.mono}`, color: colors.muted }}>
                {t.opened}
              </span>
            </div>
          ))}
        </section>

        {/* completed trades */}
        <section style={cardFlush}>
          <div style={sectionHead}>Completed trades</div>
          {journalClosed.map((t) => (
            <div
              key={t.ticker}
              style={{
                display: 'grid',
                gridTemplateColumns: closedCols,
                gap: 14,
                padding: '13px 22px',
                borderBottom: `1px solid ${colors.borderSoft}`,
                alignItems: 'center',
              }}
            >
              <span style={{ font: `600 13px/1 ${fonts.mono}`, color: colors.text }}>{t.ticker}</span>
              <span style={dirStyle(t.direction)}>{t.direction}</span>
              <span style={{ font: `400 12px/1.4 ${fonts.sans}`, color: colors.text3 }}>{t.outcome}</span>
              <span style={{ textAlign: 'right', font: `500 13px/1 ${fonts.mono}`, color: pnlColor(t.pnl) }}>
                {t.pnl}
              </span>
            </div>
          ))}
        </section>
      </div>

      <NewEntryForm />
    </div>
  )
}
