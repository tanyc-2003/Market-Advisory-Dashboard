import { useState, type CSSProperties } from 'react'
import { colors, fonts } from '../theme'
import { cardFlush, card } from '../styles'
import type { OpenTrade } from '../data'
import type { JournalData, JournalEntryInput, JournalCloseInput, JournalSubmitResult } from '../api'

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

const emptyRow: CSSProperties = {
  padding: '16px 22px',
  font: `400 12px/1.4 ${fonts.sans}`,
  color: colors.muted,
}

const OPEN_COLS = '80px 80px 64px 1fr 80px 64px'

// ---------------- new-entry form ----------------

function NewEntryForm({
  submitting,
  onSubmit,
}: {
  submitting: boolean
  onSubmit: (entry: JournalEntryInput) => Promise<JournalSubmitResult>
}) {
  const [hover, setHover] = useState(false)
  const [ticker, setTicker] = useState('')
  const [direction, setDirection] = useState('long')
  const [confidence, setConfidence] = useState('3')
  const [thesis, setThesis] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [flash, setFlash] = useState(false)

  const submit = async () => {
    setError(null)
    setFlash(false)
    const conf = Number(confidence)
    if (!ticker.trim()) return setError('Ticker is required.')
    if (!thesis.trim()) return setError('Thesis is required.')
    if (!Number.isInteger(conf) || conf < 1 || conf > 5) return setError('Confidence must be 1–5.')

    const result = await onSubmit({ ticker: ticker.trim(), direction, confidence: conf, thesis: thesis.trim() })
    if (result.ok) {
      setTicker('')
      setThesis('')
      setConfidence('3')
      setDirection('long')
      setFlash(true)
    } else {
      setError(result.error)
    }
  }

  return (
    <section style={{ ...card, padding: '22px 22px', position: 'sticky', top: 104 }}>
      <h2 style={{ margin: '0 0 16px', font: `600 11px/1 ${fonts.mono}`, letterSpacing: '0.12em', textTransform: 'uppercase', color: colors.muted }}>
        New entry
      </h2>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 13 }}>
        <div>
          <label style={fieldLabel}>Ticker</label>
          <input value={ticker} onChange={(e) => setTicker(e.target.value)} placeholder="e.g. NVDA" style={inputStyle} />
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <div style={{ flex: 1 }}>
            <label style={fieldLabel}>Direction</label>
            <select value={direction} onChange={(e) => setDirection(e.target.value)} style={{ ...inputStyle, cursor: 'pointer' }}>
              <option value="long">long</option>
              <option value="short">short</option>
              <option value="avoided">avoided</option>
            </select>
          </div>
          <div style={{ width: 96 }}>
            <label style={fieldLabel}>Conf. 1–5</label>
            <input value={confidence} onChange={(e) => setConfidence(e.target.value)} inputMode="numeric" style={inputStyle} />
          </div>
        </div>
        <div>
          <label style={fieldLabel}>Thesis</label>
          <textarea
            value={thesis}
            onChange={(e) => setThesis(e.target.value)}
            rows={3}
            placeholder="What is the bet, and what would invalidate it?"
            style={{ ...inputStyle, font: `400 12px/1.5 ${fonts.sans}`, resize: 'vertical' }}
          />
        </div>

        {error && <div style={{ font: `400 11px/1.4 ${fonts.sans}`, color: colors.red }}>{error}</div>}
        {flash && !error && <div style={{ font: `400 11px/1.4 ${fonts.sans}`, color: colors.green }}>Entry logged.</div>}

        <button
          onClick={submit}
          disabled={submitting}
          onMouseEnter={() => setHover(true)}
          onMouseLeave={() => setHover(false)}
          style={{
            marginTop: 4,
            background: submitting ? colors.dim : hover ? colors.blueHover : colors.blue,
            color: colors.sidebar,
            border: 'none',
            borderRadius: 8,
            padding: 11,
            font: `600 13px/1 ${fonts.sans}`,
            cursor: submitting ? 'default' : 'pointer',
            transition: 'background .12s',
          }}
        >
          {submitting ? 'Logging…' : 'Log entry'}
        </button>
      </div>
    </section>
  )
}

// ---------------- open trade row (with inline close) ----------------

function OpenTradeRow({
  t,
  onClose,
}: {
  t: OpenTrade
  onClose: (id: string, payload: JournalCloseInput) => Promise<JournalSubmitResult>
}) {
  const [editing, setEditing] = useState(false)
  const [pnl, setPnl] = useState('')
  const [reason, setReason] = useState('')
  const [validated, setValidated] = useState('true')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const closable = t.id !== ''

  const save = async () => {
    setError(null)
    const pnlNum = Number(pnl)
    if (pnl.trim() === '' || Number.isNaN(pnlNum)) return setError('Enter a P&L % (e.g. -3.1).')
    setSaving(true)
    const result = await onClose(t.id, {
      pnlPct: pnlNum,
      exitReason: reason.trim(),
      thesisValidated: validated === 'true',
    })
    setSaving(false)
    if (!result.ok) setError(result.error)
    // on success the dashboard refreshes and this row disappears from "open"
  }

  return (
    <div style={{ borderBottom: `1px solid ${colors.borderSoft}` }}>
      <div style={{ display: 'grid', gridTemplateColumns: OPEN_COLS, gap: 14, padding: '13px 22px', alignItems: 'center' }}>
        <span style={{ font: `600 13px/1 ${fonts.mono}`, color: colors.text }}>{t.ticker}</span>
        <span style={dirStyle(t.direction)}>{t.direction}</span>
        <span style={{ font: `500 12px/1 ${fonts.mono}`, color: colors.text2 }}>{t.conf}/5</span>
        <span style={{ font: `400 12px/1.4 ${fonts.sans}`, color: colors.text3 }}>{t.thesis}</span>
        <span style={{ textAlign: 'right', font: `400 11px/1 ${fonts.mono}`, color: colors.muted }}>{t.opened}</span>
        <span style={{ textAlign: 'right' }}>
          {closable && !editing && (
            <button
              onClick={() => setEditing(true)}
              style={{
                background: 'transparent',
                color: colors.text3,
                border: `1px solid ${colors.border}`,
                borderRadius: 6,
                padding: '4px 9px',
                font: `500 10px/1 ${fonts.mono}`,
                cursor: 'pointer',
              }}
            >
              Close
            </button>
          )}
        </span>
      </div>

      {editing && (
        <div
          style={{
            padding: '0 22px 16px',
            display: 'flex',
            alignItems: 'flex-end',
            gap: 10,
            flexWrap: 'wrap',
          }}
        >
          <div style={{ width: 96 }}>
            <label style={fieldLabel}>P&amp;L %</label>
            <input value={pnl} onChange={(e) => setPnl(e.target.value)} placeholder="-3.1" inputMode="decimal" style={inputStyle} />
          </div>
          <div style={{ width: 150 }}>
            <label style={fieldLabel}>Outcome</label>
            <select value={validated} onChange={(e) => setValidated(e.target.value)} style={{ ...inputStyle, cursor: 'pointer' }}>
              <option value="true">Thesis confirmed</option>
              <option value="false">Invalidated</option>
            </select>
          </div>
          <div style={{ flex: 1, minWidth: 160 }}>
            <label style={fieldLabel}>Exit reason</label>
            <input
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="e.g. vol spike, cut early"
              style={{ ...inputStyle, font: `400 12px/1.4 ${fonts.sans}` }}
            />
          </div>
          <button
            onClick={save}
            disabled={saving}
            style={{
              background: saving ? colors.dim : colors.blue,
              color: colors.sidebar,
              border: 'none',
              borderRadius: 7,
              padding: '9px 14px',
              font: `600 12px/1 ${fonts.sans}`,
              cursor: saving ? 'default' : 'pointer',
            }}
          >
            {saving ? 'Saving…' : 'Save'}
          </button>
          <button
            onClick={() => {
              setEditing(false)
              setError(null)
            }}
            disabled={saving}
            style={{
              background: 'transparent',
              color: colors.text3,
              border: `1px solid ${colors.border}`,
              borderRadius: 7,
              padding: '9px 14px',
              font: `500 12px/1 ${fonts.sans}`,
              cursor: 'pointer',
            }}
          >
            Cancel
          </button>
          {error && <div style={{ width: '100%', font: `400 11px/1.4 ${fonts.sans}`, color: colors.red }}>{error}</div>}
        </div>
      )}
    </div>
  )
}

// ---------------- view ----------------

export default function JournalView({
  journal,
  submitting,
  onSubmit,
  onClose,
}: {
  journal: JournalData
  submitting: boolean
  onSubmit: (entry: JournalEntryInput) => Promise<JournalSubmitResult>
  onClose: (id: string, payload: JournalCloseInput) => Promise<JournalSubmitResult>
}) {
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
              gridTemplateColumns: OPEN_COLS,
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
            <span />
          </div>
          {journal.open.length === 0 && <div style={emptyRow}>No open trades. Log one to get started.</div>}
          {journal.open.map((t, i) => (
            <OpenTradeRow key={t.id || `${t.ticker}-${i}`} t={t} onClose={onClose} />
          ))}
        </section>

        {/* completed trades */}
        <section style={cardFlush}>
          <div style={sectionHead}>Completed trades</div>
          {journal.closed.length === 0 && <div style={emptyRow}>No completed trades yet.</div>}
          {journal.closed.map((t, i) => (
            <div
              key={`${t.ticker}-${i}`}
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
              <span style={{ textAlign: 'right', font: `500 13px/1 ${fonts.mono}`, color: pnlColor(t.pnl) }}>{t.pnl}</span>
            </div>
          ))}
        </section>
      </div>

      <NewEntryForm submitting={submitting} onSubmit={onSubmit} />
    </div>
  )
}
