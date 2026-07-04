import { useState, type CSSProperties } from 'react'
import {
  colors,
  fonts,
  statusColor,
  fmtPct,
  fmtProb,
  pos,
  pUpColor,
  verdictColor,
  kindColor,
  buildFan,
  alphaVariants,
  type ForecastBand,
} from '../theme'
import { card, sectionLabel } from '../styles'
import type { Layer, Asset, NotesData, RecommendationChanges, Stress } from '../data'
import type { MarketState } from '../api'

interface OverviewProps {
  layers: Layer[]
  marketState: MarketState
  assets: Asset[]
  unknowns: string[]
  kellyCap: string
  stress: Stress
  notes: NotesData
  changes: RecommendationChanges
  selectedTicker: string
  onSelectTicker: (t: string) => void
  onAddNote: (body: string, ticker: string | null) => void
  onMarkNoteRead: (id: string) => void
}

const previewChip: CSSProperties = {
  padding: '5px 9px',
  borderRadius: 6,
  background: 'rgba(224,176,74,0.09)',
  border: '1px solid rgba(224,176,74,0.28)',
  font: `400 10px/1.4 ${fonts.sans}`,
  color: colors.amberText,
}

/** √t-widening fallback fan from the 10-day distribution when the analog engine
 *  hasn't supplied per-horizon bands (e.g. representative rows). */
function approxFan(a: Asset): ForecastBand[] {
  return [1, 3, 5, 10].map((h) => {
    const s = Math.sqrt(h / 10)
    const p50 = a.p50 * (h / 10)
    return { h, p50, p5: p50 - (a.p50 - a.p5) * s, p95: p50 + (a.p95 - a.p50) * s }
  })
}

function StressGauge({ stress }: { stress: Stress }) {
  const arcLen = Math.PI * 86
  const composite = stress.composite ?? 0
  const frac = Math.max(0, Math.min(100, composite)) / 100
  const arcColor = { calm: colors.green, normal: colors.blue, elevated: colors.amber, stressed: colors.red }[stress.level] ?? colors.blue
  const rad = ((180 - frac * 180) * Math.PI) / 180
  const needleX = (100 + 76 * Math.cos(rad)).toFixed(1)
  const needleY = (100 - 76 * Math.sin(rad)).toFixed(1)

  return (
    <section style={{ ...card, padding: '20px 26px', display: 'flex', alignItems: 'center', gap: 28 }}>
      <div style={{ flex: 'none', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <svg viewBox="0 0 200 112" width="180" height="101">
          <path d="M14,100 A86,86 0 0 1 186,100" fill="none" stroke={colors.borderMid} strokeWidth="14" strokeLinecap="round" />
          <path
            d="M14,100 A86,86 0 0 1 186,100"
            fill="none"
            stroke={arcColor}
            strokeWidth="14"
            strokeLinecap="round"
            strokeDasharray={`${(arcLen * frac).toFixed(1)} ${arcLen.toFixed(1)}`}
          />
          <line x1="100" y1="100" x2={needleX} y2={needleY} stroke={colors.text} strokeWidth="3" strokeLinecap="round" />
          <circle cx="100" cy="100" r="5.5" fill={colors.text} />
        </svg>
        <div style={{ marginTop: -6, font: `600 26px/1 ${fonts.mono}`, color: arcColor }}>
          {stress.composite === null ? '—' : composite.toFixed(0)}
        </div>
        <div style={{ marginTop: 4, font: `500 11px/1 ${fonts.mono}`, color: colors.muted, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
          {stress.level}
        </div>
      </div>
      <div style={{ flex: 'none', width: 1, alignSelf: 'stretch', background: colors.borderMid }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 11 }}>
          <h2 style={sectionLabel}>Composite market-stress gauge</h2>
          <span style={{ font: `500 10px/1 ${fonts.mono}`, color: colors.muted, border: `1px solid ${colors.border}`, borderRadius: 4, padding: '3px 6px' }}>
            not a model
          </span>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {stress.components.map((c, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <span style={{ width: 170, flex: 'none', font: `400 12px/1.2 ${fonts.sans}`, color: colors.text3 }}>{c.name}</span>
              <div style={{ flex: 1, height: 7, borderRadius: 4, background: colors.track, overflow: 'hidden' }}>
                <div style={{ height: '100%', width: `${Math.max(0, Math.min(100, c.value)).toFixed(1)}%`, borderRadius: 4, background: arcColor }} />
              </div>
              <span style={{ width: 56, flex: 'none', textAlign: 'right', font: `500 12px/1 ${fonts.mono}`, color: colors.text2 }}>{c.value.toFixed(0)}</span>
              <span style={{ width: 60, flex: 'none', textAlign: 'right', font: `400 10px/1 ${fonts.mono}`, color: colors.muted }}>wt {c.weight.toFixed(2)}</span>
            </div>
          ))}
        </div>
        {stress.weighting && <p style={{ margin: '12px 0 0', font: `400 11px/1.5 ${fonts.sans}`, color: colors.muted2 }}>{stress.weighting}</p>}
      </div>
    </section>
  )
}

function GateStrip({ layers }: { layers: Layer[] }) {
  return (
    <section>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 13 }}>
        <h2 style={sectionLabel}>Layer 0 — Validation gate</h2>
        <span style={{ font: `400 11px/1 ${fonts.sans}`, color: colors.muted }}>No output is treated as evidence until it passes sign-off.</span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(168px,1fr))', gap: 8 }}>
        {layers.map((L) => {
          const col = statusColor(L.status)
          const metric =
            L.status === 'production' ? 'All criteria pass' : L.status === 'research_preview' ? (L.rationale || '').split(' — ')[0] : 'Output hidden'
          return (
            <div key={L.id} title={L.rationale} style={{ ...card, padding: '11px 12px', borderRadius: 8, display: 'flex', flexDirection: 'column', gap: 7 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', flex: 'none', background: col }} />
                <span style={{ font: `500 11px/1 ${fonts.mono}`, color: colors.muted }}>{L.id}</span>
                <span style={{ font: `500 12px/1.1 ${fonts.sans}`, color: colors.text2, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {L.name}
                </span>
              </div>
              <div style={{ font: `500 10px/1.3 ${fonts.mono}`, color: colors.muted2 }}>{metric}</div>
            </div>
          )
        })}
      </div>
    </section>
  )
}

function MarketStateCard({ ms }: { ms: MarketState }) {
  const dominant = ms.states[0]
  return (
    <section style={card}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 18 }}>
        <div>
          <h2 style={sectionLabel}>Layer 1 — Market state</h2>
          <div style={{ marginTop: 10, display: 'flex', alignItems: 'baseline', gap: 11 }}>
            <span style={{ font: `600 24px/1 ${fonts.sans}`, letterSpacing: '-0.01em', color: colors.text }}>{dominant?.name ?? '—'}</span>
            <span style={{ font: `500 13px/1 ${fonts.mono}`, color: colors.green }}>{dominant ? (dominant.prob * 100).toFixed(0) + '%' : ''}</span>
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ font: `500 10px/1 ${fonts.mono}`, color: colors.muted, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Uncertainty</div>
          <div style={{ marginTop: 6, font: `500 16px/1 ${fonts.mono}`, color: colors.text2 }}>{ms.uncertainty}</div>
        </div>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 11 }}>
        {ms.states.map((s, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ width: 96, flex: 'none', font: `400 12px/1.2 ${fonts.sans}`, color: colors.text3 }}>{s.name}</span>
            <div style={{ flex: 1, height: 8, borderRadius: 4, background: colors.track, overflow: 'hidden' }}>
              <div style={{ height: '100%', width: `${(s.prob * 100).toFixed(1)}%`, borderRadius: 4, background: i === 0 ? colors.blue : colors.blueDim }} />
            </div>
            <span style={{ width: 48, flex: 'none', textAlign: 'right', font: `500 12px/1 ${fonts.mono}`, color: colors.text2 }}>{(s.prob * 100).toFixed(0)}%</span>
          </div>
        ))}
      </div>
      {ms.transition && (
        <div style={{ marginTop: 18, padding: '12px 14px', borderRadius: 8, background: colors.cardInner, border: `1px solid ${colors.borderMid}`, display: 'flex', alignItems: 'flex-start', gap: 10 }}>
          <span style={{ font: `500 9px/1.6 ${fonts.mono}`, color: colors.blue, letterSpacing: '0.06em', border: '1px solid rgba(122,162,247,0.4)', borderRadius: 4, padding: '3px 5px' }}>
            TRANSITION
          </span>
          <span style={{ font: `400 12px/1.5 ${fonts.sans}`, color: colors.muted4 }}>{ms.transition}</span>
        </div>
      )}
    </section>
  )
}

function SizingCard({ asset, kellyCap }: { asset: Asset; kellyCap: string }) {
  const sz = asset.sizing
  const ladder = [
    { label: 'Raw Kelly', value: sz.raw },
    { label: 'Standard haircut (×0.5)', value: sz.std },
    { label: 'Regime-aware haircut', value: sz.regime },
    { label: 'After 0.20 cap', value: sz.displayed },
  ]
  return (
    <section style={{ ...card, display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
        <h2 style={sectionLabel}>Layer 10 — Sizing</h2>
        <span style={{ font: `500 11px/1 ${fonts.mono}`, color: colors.text2 }}>{asset.ticker}</span>
      </div>
      <div style={{ ...previewChip, margin: '4px 0 2px' }}>Research preview — not validated for live decision support.</div>
      <div style={{ margin: '18px 0', textAlign: 'center' }}>
        <div style={{ font: `500 10px/1 ${fonts.mono}`, color: colors.muted, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Displayed Kelly fraction</div>
        <div style={{ marginTop: 8, font: `600 44px/1 ${fonts.mono}`, color: colors.blue }}>{sz.displayed.toFixed(2)}</div>
        <div style={{ marginTop: 6, font: `400 11px/1 ${fonts.mono}`, color: colors.muted }}>hard cap {kellyCap}</div>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 1, background: colors.borderMid, border: `1px solid ${colors.borderMid}`, borderRadius: 8, overflow: 'hidden' }}>
        {ladder.map((row, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 13px', background: colors.cardInner }}>
            <span style={{ font: `400 12px/1.2 ${fonts.sans}`, color: colors.text3 }}>{row.label}</span>
            <span style={{ font: `500 13px/1 ${fonts.mono}`, color: colors.text2 }}>{row.value.toFixed(2)}</span>
          </div>
        ))}
      </div>
    </section>
  )
}

function CaseCard({ asset }: { asset: Asset }) {
  const c = asset.case
  return (
    <section style={{ ...card, display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
        <h2 style={sectionLabel}>Case for / against</h2>
        {c &&
          (() => {
            const v = alphaVariants(verdictColor(c.verdict))
            return (
              <span style={{ font: `600 10px/1 ${fonts.mono}`, letterSpacing: '0.05em', textTransform: 'uppercase', padding: '4px 8px', borderRadius: 5, color: v.fg, background: v.bg, border: `1px solid ${v.border}` }}>
                {c.verdict}
              </span>
            )
          })()}
      </div>
      {!c ? (
        <div style={{ font: `400 12px/1.5 ${fonts.sans}`, color: colors.muted, flex: 1 }}>
          Synthesis unavailable for this row — the bull/bear case is composed from live analog outputs.
        </div>
      ) : (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, flex: 1 }}>
            {([['Bull', colors.green, '+', c.bull], ['Bear', colors.red, '−', c.bear]] as const).map(([label, col, sign, items]) => (
              <div key={label}>
                <div style={{ font: `600 10px/1 ${fonts.mono}`, color: col, letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 9 }}>{label}</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {items.map((b, i) => (
                    <div key={i} style={{ display: 'flex', gap: 7, alignItems: 'flex-start' }}>
                      <span style={{ color: col, font: `500 11px/1.5 ${fonts.mono}`, flex: 'none' }}>{sign}</span>
                      <span style={{ font: `400 12px/1.45 ${fonts.sans}`, color: colors.muted4 }}>{b}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
          <div style={{ marginTop: 12, font: `400 11px/1 ${fonts.mono}`, color: colors.muted }}>confidence: {c.confidence}</div>
        </>
      )}
    </section>
  )
}

function ForecastFan({ asset }: { asset: Asset }) {
  const forecast = asset.forecast && asset.forecast.length ? asset.forecast : approxFan(asset)
  const approx = asset.forecast && asset.forecast.length ? !!asset.forecastApprox : true
  const fan = buildFan(forecast)
  return (
    <section style={card}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
        <h2 style={sectionLabel}>Layer 2/3/7 — Forecast fan · {asset.ticker}</h2>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {approx && (
            <span
              title="Band scaled by √time until per-horizon analog features are ingested"
              style={{ font: `500 10px/1 ${fonts.mono}`, color: colors.amber, border: '1px solid rgba(224,176,74,0.4)', borderRadius: 4, padding: '3px 6px', cursor: 'help' }}
            >
              ≈ approx
            </span>
          )}
          <span style={{ font: `400 11px/1 ${fonts.sans}`, color: colors.muted }}>median path · p5–p95 band, widening with horizon</span>
        </div>
      </div>
      <svg viewBox="0 0 760 150" width="100%" height="150" preserveAspectRatio="none" style={{ display: 'block' }}>
        <line x1="20" y1={fan.zeroY} x2="740" y2={fan.zeroY} stroke={colors.borderMid} strokeWidth="1" strokeDasharray="4 4" />
        <path d={fan.bandPath} fill="rgba(122,162,247,0.16)" stroke="none" />
        <polyline points={fan.linePoints} fill="none" stroke={colors.blue} strokeWidth="2.5" />
        {fan.dots.map((d, i) => (
          <circle key={i} cx={d.x} cy={d.y} r="3.5" fill={colors.blue} stroke={colors.card} strokeWidth="1.5" />
        ))}
      </svg>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 2, font: `400 10px/1 ${fonts.mono}`, color: colors.muted }}>
        <span>h=1d</span>
        <span>h=3d</span>
        <span>h=5d</span>
        <span>h=10d</span>
      </div>
    </section>
  )
}

function AssetRow({ a, selected, onSelect }: { a: Asset; selected: boolean; onSelect: () => void }) {
  const [hover, setHover] = useState(false)
  const hov = !selected && hover
  const l5 = pos(a.p5)
  const l25 = pos(a.p25)
  const l50 = pos(a.p50)
  const l75 = pos(a.p75)
  const l95 = pos(a.p95)
  const pUp = a.pUp ?? null
  const pUpCol = pUp === null ? colors.muted : pUpColor(pUp)
  const dot: CSSProperties = { position: 'absolute', top: '50%', transform: 'translateY(-50%)' }

  return (
    <div
      onClick={onSelect}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        padding: '15px 20px',
        borderBottom: `1px solid ${colors.borderSoft}`,
        cursor: 'pointer',
        transition: 'background .12s',
        background: selected ? colors.selRow : hov ? colors.cardInner2 : 'transparent',
        boxShadow: selected ? `inset 3px 0 0 ${colors.blue}` : 'none',
      }}
    >
      <div style={{ display: 'grid', gridTemplateColumns: '150px 84px 1fr 96px 110px', gap: 16, alignItems: 'center' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', flex: 'none', background: selected ? colors.blue : 'transparent' }} />
            <span style={{ font: `600 14px/1 ${fonts.mono}`, color: colors.text }}>{a.ticker}</span>
          </div>
          <div style={{ marginTop: 4, marginLeft: 16, font: `400 11px/1 ${fonts.sans}`, color: colors.muted }}>{a.sector}</div>
        </div>
        <div style={{ font: `500 13px/1 ${fonts.mono}`, color: colors.text2 }}>
          {a.n}
          <span style={{ color: colors.muted, fontSize: 10 }}> eff</span>
        </div>
        <div>
          <div style={{ position: 'relative', height: 22 }}>
            <div style={{ position: 'absolute', top: '50%', left: 0, right: 0, height: 1, background: colors.borderMid }} />
            <div style={{ ...dot, top: 0, bottom: 0, left: `${pos(0)}%`, width: 1, background: colors.dim, transform: 'none' }} />
            <div style={{ ...dot, height: 2, background: colors.blueDeep, left: `${l5}%`, width: `${l95 - l5}%`, borderRadius: 1 }} />
            <div style={{ ...dot, height: 12, borderRadius: 3, background: 'rgba(122,162,247,0.28)', border: '1px solid rgba(122,162,247,0.55)', left: `${l25}%`, width: `${l75 - l25}%` }} />
            <div style={{ position: 'absolute', top: '50%', transform: 'translate(-50%,-50%)', width: 3, height: 18, borderRadius: 2, background: colors.blue, left: `${l50}%` }} />
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 3, font: `400 10px/1 ${fonts.mono}`, color: colors.muted }}>
            <span>{fmtPct(a.p5, true)}</span>
            <span style={{ color: colors.text3 }}>{fmtPct(a.p50, true)}</span>
            <span>{fmtPct(a.p95, true)}</span>
          </div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span style={{ font: `600 11px/1 ${fonts.mono}`, color: pUpCol }}>P↑ {fmtProb(pUp)}</span>
          {a.pVolShift !== null && a.pVolShift !== undefined && (
            <span style={{ font: `500 10px/1 ${fonts.mono}`, color: colors.amberText2 }}>Δvol {fmtProb(a.pVolShift)}</span>
          )}
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ font: `500 13px/1 ${fonts.mono}`, color: colors.text2 }}>{(a.hitRate * 100).toFixed(0)}%</div>
          <div style={{ marginTop: 4, font: `500 10px/1 ${fonts.mono}`, color: colors.muted }}>{a.conf}</div>
        </div>
      </div>
      {a.disagreement && a.disagreementNote && (
        <div style={{ marginTop: 11, padding: '7px 11px', borderRadius: 6, background: 'rgba(224,108,108,0.08)', border: '1px solid rgba(224,108,108,0.26)', display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ color: colors.red, fontSize: 10 }}>●</span>
          <span style={{ font: `400 11px/1.4 ${fonts.sans}`, color: colors.redText }}>{a.disagreementNote}</span>
        </div>
      )}
      <div style={{ marginTop: 9, marginLeft: 16, display: 'flex', gap: 7, flexWrap: 'wrap' }}>
        {a.drivers.map((d, i) => (
          <span key={i} style={{ font: `400 10px/1 ${fonts.mono}`, color: colors.muted3, background: colors.cardInner, border: `1px solid ${colors.borderMid}`, borderRadius: 5, padding: '4px 7px' }}>
            {d}
          </span>
        ))}
      </div>
    </div>
  )
}

function NotesInbox({
  notes,
  selectedTicker,
  onAddNote,
  onMarkNoteRead,
}: {
  notes: NotesData
  selectedTicker: string
  onAddNote: (b: string, t: string | null) => void
  onMarkNoteRead: (id: string) => void
}) {
  const [unreadOnly, setUnreadOnly] = useState(false)
  const [draft, setDraft] = useState('')
  const items = unreadOnly ? notes.items.filter((n) => !n.read) : notes.items

  const submit = () => {
    const text = draft.trim()
    if (!text) return
    onAddNote(text, selectedTicker)
    setDraft('')
  }

  return (
    <section style={{ ...card, display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
          <h2 style={sectionLabel}>Layer 7 — Notes inbox</h2>
          {notes.unread > 0 && (
            <span style={{ font: `600 10px/1 ${fonts.mono}`, color: colors.sidebar, background: colors.blue, borderRadius: 9, padding: '2px 7px' }}>{notes.unread}</span>
          )}
        </div>
        <div
          onClick={() => setUnreadOnly((v) => !v)}
          style={{
            cursor: 'pointer',
            font: `500 10px/1 ${fonts.mono}`,
            letterSpacing: '0.04em',
            padding: '5px 9px',
            borderRadius: 6,
            border: `1px solid ${unreadOnly ? colors.blue : colors.border}`,
            color: unreadOnly ? colors.blue : colors.muted,
            background: unreadOnly ? 'rgba(122,162,247,0.1)' : 'transparent',
          }}
        >
          unread only
        </div>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 9, maxHeight: 340, overflowY: 'auto', paddingRight: 2 }}>
        {items.length === 0 && <div style={{ font: `400 12px/1.5 ${fonts.sans}`, color: colors.muted }}>No notes.</div>}
        {items.map((n) => {
          const kc = kindColor(n.kind)
          return (
            <div
              key={n.id}
              onClick={() => !n.read && onMarkNoteRead(n.id)}
              style={{ padding: '11px 13px', borderRadius: 8, background: colors.cardInner, border: `1px solid ${colors.borderMid}`, cursor: 'pointer', boxShadow: n.read ? 'none' : `inset 2px 0 0 ${colors.blue}` }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 5 }}>
                <span style={{ font: `500 9px/1 ${fonts.mono}`, letterSpacing: '0.05em', textTransform: 'uppercase', padding: '2px 6px', borderRadius: 4, color: kc, background: kc + '1a' }}>{n.kind}</span>
                {n.ticker && <span style={{ font: `600 11px/1 ${fonts.mono}`, color: colors.blue }}>{n.ticker}</span>}
                <span style={{ flex: 1 }} />
                <span style={{ font: `400 10px/1 ${fonts.mono}`, color: '#5a6270' }}>{n.createdAt}</span>
              </div>
              <div style={{ font: `400 12px/1.45 ${fonts.sans}`, color: n.read ? colors.muted2 : colors.text2 }}>{n.body}</div>
            </div>
          )
        })}
      </div>
      <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && submit()}
          placeholder="Add a note…"
          style={{ flex: 1, background: colors.cardInner, color: colors.text, border: `1px solid ${colors.border}`, borderRadius: 7, padding: '9px 11px', font: `400 12px/1 ${fonts.sans}`, outline: 'none' }}
        />
        <button onClick={submit} style={{ background: colors.blue, color: colors.sidebar, border: 'none', borderRadius: 7, padding: '0 16px', font: `600 12px/1 ${fonts.sans}`, cursor: 'pointer' }}>
          Add
        </button>
      </div>
    </section>
  )
}

function ChangeLog({ changes }: { changes: RecommendationChanges }) {
  return (
    <section style={card}>
      <h2 style={{ ...sectionLabel, marginBottom: 16 }}>What changed — decision log</h2>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 1, background: colors.borderMid, border: `1px solid ${colors.borderMid}`, borderRadius: 8, overflow: 'hidden' }}>
        {changes.items.length === 0 && <div style={{ padding: '13px 15px', background: colors.cardInner, font: `400 12px/1.5 ${fonts.sans}`, color: colors.muted }}>No recorded changes yet.</div>}
        {changes.items.map((c, i) => (
          <div key={i} style={{ display: 'grid', gridTemplateColumns: '70px 100px 1fr 90px 24px', gap: 14, alignItems: 'center', padding: '11px 15px', background: colors.cardInner }}>
            <span style={{ font: `600 12px/1 ${fonts.mono}`, color: colors.text }}>{c.ticker}</span>
            <span style={{ font: `400 11px/1 ${fonts.sans}`, color: colors.muted3 }}>{c.field}</span>
            <span style={{ font: `500 12px/1 ${fonts.mono}`, color: colors.text2 }}>
              {c.prev} <span style={{ color: colors.dimText }}>→</span> {c.next ?? c.new}
            </span>
            <span style={{ textAlign: 'right', font: `400 10px/1 ${fonts.mono}`, color: colors.muted }}>{c.changedAt}</span>
            {!c.guardPassed && (
              <span title="Guard check failed" style={{ color: colors.red, fontSize: 12 }}>⚑</span>
            )}
          </div>
        ))}
      </div>
    </section>
  )
}

export default function OverviewView({
  layers,
  marketState,
  assets,
  unknowns,
  kellyCap,
  stress,
  notes,
  changes,
  selectedTicker,
  onSelectTicker,
  onAddNote,
  onMarkNoteRead,
}: OverviewProps) {
  const selected = assets.find((a) => a.ticker === selectedTicker) ?? assets[0]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <StressGauge stress={stress} />
      <GateStrip layers={layers} />

      <div style={{ display: 'grid', gridTemplateColumns: '1.15fr 0.85fr 1fr', gap: 18 }}>
        <MarketStateCard ms={marketState} />
        {selected && <SizingCard asset={selected} kellyCap={kellyCap} />}
        {selected && <CaseCard asset={selected} />}
      </div>

      {selected && <ForecastFan asset={selected} />}

      <section>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
          <h2 style={sectionLabel}>Layers 2 · 3 · 7 — Watchlist</h2>
          <span style={{ font: `400 11px/1 ${fonts.sans}`, color: colors.muted }}>Forward 10-day return distribution from historical analogs · select a row to focus sizing</span>
        </div>
        <div style={{ marginBottom: 14, padding: '7px 11px', borderRadius: 7, background: 'rgba(224,176,74,0.09)', border: '1px solid rgba(224,176,74,0.28)', display: 'flex', alignItems: 'center', gap: 9 }}>
          <span style={{ color: colors.amber, fontSize: 11 }}>▲</span>
          <span style={{ font: `500 11px/1.4 ${fonts.sans}`, color: colors.amberText }}>Research preview — not validated for live decision support.</span>
          <span style={{ font: `400 11px/1.4 ${fonts.sans}`, color: colors.amberText2 }}>Analog engine deflated Sharpe below the 0.95 floor.</span>
        </div>
        <div style={{ background: colors.card, border: `1px solid ${colors.border}`, borderRadius: 12, overflow: 'hidden' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '150px 84px 1fr 96px 110px', gap: 16, padding: '11px 20px', borderBottom: `1px solid ${colors.borderMid}`, font: `500 10px/1 ${fonts.mono}`, color: colors.muted, textTransform: 'uppercase', letterSpacing: '0.07em' }}>
            <span>Asset</span>
            <span>Analogs</span>
            <span>Forward 10d return · p5 — p25 / p50 / p75 — p95</span>
            <span>P↑10d · Δvol</span>
            <span style={{ textAlign: 'right' }}>Hit rate · conf.</span>
          </div>
          {assets.map((a) => (
            <AssetRow key={a.ticker} a={a} selected={a.ticker === (selected?.ticker ?? '')} onSelect={() => onSelectTicker(a.ticker)} />
          ))}
        </div>
      </section>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 18 }}>
        <NotesInbox notes={notes} selectedTicker={selectedTicker} onAddNote={onAddNote} onMarkNoteRead={onMarkNoteRead} />
        <section style={card}>
          <h2 style={{ ...sectionLabel, margin: '0 0 16px' }}>⚠ What this system does not know</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 11 }}>
            {unknowns.map((u, i) => (
              <div key={i} style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                <span style={{ color: colors.muted, font: `500 11px/1.5 ${fonts.mono}`, flex: 'none' }}>—</span>
                <span style={{ font: `400 12px/1.5 ${fonts.sans}`, color: colors.text3 }}>{u}</span>
              </div>
            ))}
          </div>
        </section>
      </div>

      <ChangeLog changes={changes} />
    </div>
  )
}
