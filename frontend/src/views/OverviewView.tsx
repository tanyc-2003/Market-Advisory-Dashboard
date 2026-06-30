import { useState } from 'react'
import { colors, fonts, statusColor, fmtPct, pos } from '../theme'
import { card, sectionLabel, microLabel, amberBanner } from '../styles'
import type { Layer, Asset, Alert } from '../data'
import type { MarketState } from '../api'

// ---------------- gate strip (Layer 0) ----------------

function GateStrip({ layers }: { layers: Layer[] }) {
  return (
    <section>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 13 }}>
        <h2 style={sectionLabel}>Layer 0 — Validation gate</h2>
        <span style={{ font: `400 11px/1 ${fonts.sans}`, color: colors.muted }}>
          No output is treated as evidence until it passes sign-off.
        </span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(168px,1fr))', gap: 8 }}>
        {layers.map((L) => {
          const metric =
            L.status === 'production'
              ? 'All criteria pass'
              : L.status === 'research_preview'
                ? L.rationale.split(' — ')[0]
                : 'Output hidden'
          return (
            <div
              key={L.id}
              title={L.rationale}
              style={{
                background: colors.card,
                border: `1px solid ${colors.border}`,
                borderRadius: 8,
                padding: '11px 12px',
                display: 'flex',
                flexDirection: 'column',
                gap: 7,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', flex: 'none', background: statusColor(L.status) }} />
                <span style={{ font: `500 11px/1 ${fonts.mono}`, color: colors.muted }}>{L.id}</span>
                <span
                  style={{
                    font: `500 12px/1.1 ${fonts.sans}`,
                    color: colors.text2,
                    flex: 1,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
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

// ---------------- market state (Layer 1) ----------------

function MarketStatePanel({ marketState }: { marketState: MarketState }) {
  const { states, uncertainty, transition, disclosure } = marketState
  return (
    <section style={card}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 18 }}>
        <div>
          <h2 style={sectionLabel}>Layer 1 — Market state</h2>
          <div style={{ marginTop: 10, display: 'flex', alignItems: 'baseline', gap: 11 }}>
            <span style={{ font: `600 24px/1 ${fonts.sans}`, letterSpacing: '-0.01em', color: colors.text }}>
              {states[0]?.name}
            </span>
            <span style={{ font: `500 13px/1 ${fonts.mono}`, color: colors.green }}>
              {((states[0]?.prob ?? 0) * 100).toFixed(0)}%
            </span>
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={microLabel}>Uncertainty</div>
          <div style={{ marginTop: 6, font: `500 16px/1 ${fonts.mono}`, color: colors.text2 }}>{uncertainty}</div>
        </div>
      </div>

      {disclosure && (
        <div
          style={{
            ...amberBanner,
            margin: '0 0 16px',
            padding: '7px 11px',
            display: 'flex',
            alignItems: 'flex-start',
            gap: 9,
          }}
        >
          <span style={{ color: colors.amber, fontSize: 11, lineHeight: 1.5 }}>▲</span>
          <span style={{ font: `400 11px/1.45 ${fonts.sans}`, color: colors.amberText }}>{disclosure}</span>
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 11 }}>
        {states.map((s, i) => (
          <div key={s.name} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ width: 96, flex: 'none', font: `400 12px/1.2 ${fonts.sans}`, color: colors.text3 }}>
              {s.name}
            </span>
            <div style={{ flex: 1, height: 8, borderRadius: 4, background: colors.track, overflow: 'hidden' }}>
              <div
                style={{
                  height: '100%',
                  width: `${(s.prob * 100).toFixed(1)}%`,
                  borderRadius: 4,
                  background: i === 0 ? colors.blue : colors.blueDim,
                }}
              />
            </div>
            <span style={{ width: 48, flex: 'none', textAlign: 'right', font: `500 12px/1 ${fonts.mono}`, color: colors.text2 }}>
              {(s.prob * 100).toFixed(0)}%
            </span>
          </div>
        ))}
      </div>

      <div
        style={{
          marginTop: 18,
          padding: '12px 14px',
          borderRadius: 8,
          background: colors.cardInner,
          border: `1px solid ${colors.borderMid}`,
          display: 'flex',
          alignItems: 'flex-start',
          gap: 10,
        }}
      >
        <span
          style={{
            font: `500 9px/1.6 ${fonts.mono}`,
            color: colors.blue,
            letterSpacing: '0.06em',
            border: '1px solid rgba(122,162,247,0.4)',
            borderRadius: 4,
            padding: '3px 5px',
          }}
        >
          TRANSITION
        </span>
        <span style={{ font: `400 12px/1.5 ${fonts.sans}`, color: colors.muted4 }}>{transition}</span>
      </div>
    </section>
  )
}

// ---------------- sizing (Layer 10) ----------------

function SizingPanel({
  assets,
  selectedTicker,
  sizingNote,
  kellyCap,
}: {
  assets: Asset[]
  selectedTicker: string
  sizingNote: string
  kellyCap: string
}) {
  const selA = assets.find((a) => a.ticker === selectedTicker) ?? assets[0]
  const sz = selA.sizing
  const ladder = [
    { label: 'Raw Kelly', value: sz.raw.toFixed(2) },
    { label: 'Standard haircut (×0.5)', value: sz.std.toFixed(2) },
    { label: 'Regime-aware haircut', value: sz.regime.toFixed(2) },
    { label: `After ${kellyCap} cap`, value: sz.displayed.toFixed(2) },
  ]
  return (
    <section style={{ ...card, display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
        <h2 style={sectionLabel}>Layer 10 — Sizing</h2>
        <span style={{ font: `500 11px/1 ${fonts.mono}`, color: colors.text2 }}>{selectedTicker}</span>
      </div>
      <div
        style={{
          ...amberBanner,
          margin: '4px 0 2px',
          padding: '5px 9px',
          borderRadius: 6,
          font: `400 10px/1.4 ${fonts.sans}`,
          color: colors.amberText,
        }}
      >
        Research preview — not validated for live decision support.
      </div>

      <div style={{ margin: '18px 0', textAlign: 'center' }}>
        <div style={microLabel}>Displayed Kelly fraction</div>
        <div style={{ marginTop: 8, font: `600 44px/1 ${fonts.mono}`, color: colors.blue }}>
          {sz.displayed.toFixed(2)}
        </div>
        <div style={{ marginTop: 6, font: `400 11px/1 ${fonts.mono}`, color: colors.muted }}>hard cap {kellyCap}</div>
      </div>

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
        {ladder.map((row) => (
          <div
            key={row.label}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '10px 13px',
              background: colors.cardInner,
            }}
          >
            <span style={{ font: `400 12px/1.2 ${fonts.sans}`, color: colors.text3 }}>{row.label}</span>
            <span style={{ font: `500 13px/1 ${fonts.mono}`, color: colors.text2 }}>{row.value}</span>
          </div>
        ))}
      </div>
      <p style={{ margin: '14px 0 0', font: `400 11px/1.5 ${fonts.sans}`, color: colors.muted2 }}>{sizingNote}</p>
    </section>
  )
}

// ---------------- watchlist (Layers 2 · 3 · 7) ----------------

function DistributionTrack({ a }: { a: Asset }) {
  const l5 = pos(a.p5)
  const l25 = pos(a.p25)
  const l50 = pos(a.p50)
  const l75 = pos(a.p75)
  const l95 = pos(a.p95)
  return (
    <div>
      <div style={{ position: 'relative', height: 22 }}>
        <div style={{ position: 'absolute', top: '50%', left: 0, right: 0, height: 1, background: colors.borderMid }} />
        <div style={{ position: 'absolute', top: 0, bottom: 0, left: `${pos(0)}%`, width: 1, background: colors.dim }} />
        <div
          style={{
            position: 'absolute',
            top: '50%',
            transform: 'translateY(-50%)',
            height: 2,
            background: colors.blueDeep,
            left: `${l5}%`,
            width: `${l95 - l5}%`,
            borderRadius: 1,
          }}
        />
        <div
          style={{
            position: 'absolute',
            top: '50%',
            transform: 'translateY(-50%)',
            height: 12,
            borderRadius: 3,
            background: 'rgba(122,162,247,0.28)',
            border: '1px solid rgba(122,162,247,0.55)',
            left: `${l25}%`,
            width: `${l75 - l25}%`,
          }}
        />
        <div
          style={{
            position: 'absolute',
            top: '50%',
            transform: 'translate(-50%,-50%)',
            width: 3,
            height: 18,
            borderRadius: 2,
            background: colors.blue,
            left: `${l50}%`,
          }}
        />
      </div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          marginTop: 3,
          font: `400 10px/1 ${fonts.mono}`,
          color: colors.muted,
        }}
      >
        <span>{fmtPct(a.p5, true)}</span>
        <span style={{ color: colors.text3 }}>{fmtPct(a.p50, true)}</span>
        <span>{fmtPct(a.p95, true)}</span>
      </div>
    </div>
  )
}

const COLS = '150px 84px 1fr 120px'

function AssetRow({
  a,
  selected,
  onSelect,
}: {
  a: Asset
  selected: boolean
  onSelect: (t: string) => void
}) {
  const [hover, setHover] = useState(false)
  const hov = !selected && hover
  return (
    <div
      onClick={() => onSelect(a.ticker)}
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
      <div style={{ display: 'grid', gridTemplateColumns: COLS, gap: 18, alignItems: 'center' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span
              style={{
                width: 6,
                height: 6,
                borderRadius: '50%',
                flex: 'none',
                background: selected ? colors.blue : 'transparent',
              }}
            />
            <span style={{ font: `600 14px/1 ${fonts.mono}`, color: colors.text }}>{a.ticker}</span>
          </div>
          <div style={{ marginTop: 4, marginLeft: 16, font: `400 11px/1 ${fonts.sans}`, color: colors.muted }}>
            {a.sector}
          </div>
        </div>

        <div style={{ font: `500 13px/1 ${fonts.mono}`, color: colors.text2 }}>
          {a.n}
          <span style={{ color: colors.muted, fontSize: 10 }}> eff</span>
        </div>

        <DistributionTrack a={a} />

        <div style={{ textAlign: 'right' }}>
          <div style={{ font: `500 13px/1 ${fonts.mono}`, color: colors.text2 }}>{(a.hitRate * 100).toFixed(0)}%</div>
          <div style={{ marginTop: 4, font: `500 10px/1 ${fonts.mono}`, color: colors.muted }}>{a.conf}</div>
        </div>
      </div>

      {a.disagreement && (
        <div
          style={{
            marginTop: 11,
            padding: '7px 11px',
            borderRadius: 6,
            background: 'rgba(224,108,108,0.08)',
            border: '1px solid rgba(224,108,108,0.26)',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}
        >
          <span style={{ color: colors.red, fontSize: 10 }}>●</span>
          <span style={{ font: `400 11px/1.4 ${fonts.sans}`, color: colors.redText }}>{a.disagreementNote}</span>
        </div>
      )}

      <div style={{ marginTop: 9, marginLeft: 16, display: 'flex', gap: 7, flexWrap: 'wrap' }}>
        {a.drivers.map((d) => (
          <span
            key={d}
            style={{
              font: `400 10px/1 ${fonts.mono}`,
              color: colors.muted3,
              background: colors.cardInner,
              border: `1px solid ${colors.borderMid}`,
              borderRadius: 5,
              padding: '4px 7px',
            }}
          >
            {d}
          </span>
        ))}
      </div>
    </div>
  )
}

function Watchlist({
  assets,
  selectedTicker,
  onSelectTicker,
}: {
  assets: Asset[]
  selectedTicker: string
  onSelectTicker: (t: string) => void
}) {
  return (
    <section>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
        <h2 style={sectionLabel}>Layers 2 · 3 · 7 — Watchlist</h2>
        <span style={{ font: `400 11px/1 ${fonts.sans}`, color: colors.muted }}>
          Forward 10-day return distribution from historical analogs · select a row to focus sizing
        </span>
      </div>
      <div
        style={{
          ...amberBanner,
          marginBottom: 14,
          padding: '7px 11px',
          display: 'flex',
          alignItems: 'center',
          gap: 9,
        }}
      >
        <span style={{ color: colors.amber, fontSize: 11 }}>▲</span>
        <span style={{ font: `500 11px/1.4 ${fonts.sans}`, color: colors.amberText }}>
          Research preview — not validated for live decision support.
        </span>
        <span style={{ font: `400 11px/1.4 ${fonts.sans}`, color: colors.amberText2 }}>
          Analog engine deflated Sharpe 0.81 &lt; 0.95 floor.
        </span>
      </div>

      <div style={{ background: colors.card, border: `1px solid ${colors.border}`, borderRadius: 12, overflow: 'hidden' }}>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: COLS,
            gap: 18,
            padding: '11px 20px',
            borderBottom: `1px solid ${colors.borderMid}`,
            font: `500 10px/1 ${fonts.mono}`,
            color: colors.muted,
            textTransform: 'uppercase',
            letterSpacing: '0.07em',
          }}
        >
          <span>Asset</span>
          <span>Analogs</span>
          <span>Forward 10d return · p5 — p25 / p50 / p75 — p95</span>
          <span style={{ textAlign: 'right' }}>Hit rate · conf.</span>
        </div>
        {assets.map((a) => (
          <AssetRow key={a.ticker} a={a} selected={a.ticker === selectedTicker} onSelect={onSelectTicker} />
        ))}
      </div>
    </section>
  )
}

// ---------------- alerts + unknowns (Layer 7) ----------------

function sevStyle(n: 1 | 2 | 3) {
  const map = {
    3: { color: colors.red, background: 'rgba(224,108,108,0.14)' },
    2: { color: colors.amber, background: 'rgba(224,176,74,0.14)' },
    1: { color: colors.blue, background: 'rgba(122,162,247,0.14)' },
  } as const
  return map[n]
}

function AlertsAndUnknowns({ alerts, unknowns }: { alerts: Alert[]; unknowns: string[] }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 18 }}>
      <section style={card}>
        <h2 style={{ ...sectionLabel, margin: '0 0 16px' }}>Layer 7 — Active alerts</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {alerts.map((al) => {
            const sv = sevStyle(al.sev)
            return (
              <div
                key={al.title}
                style={{
                  display: 'flex',
                  gap: 11,
                  padding: '12px 14px',
                  borderRadius: 8,
                  background: colors.cardInner,
                  border: `1px solid ${colors.borderMid}`,
                }}
              >
                <span
                  style={{
                    flex: 'none',
                    width: 22,
                    height: 22,
                    borderRadius: 6,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    font: `600 11px/1 ${fonts.mono}`,
                    color: sv.color,
                    background: sv.background,
                  }}
                >
                  {al.sev}
                </span>
                <div>
                  <div style={{ font: `500 12px/1.3 ${fonts.sans}`, color: colors.text2 }}>{al.title}</div>
                  <div style={{ marginTop: 4, font: `400 11px/1.45 ${fonts.sans}`, color: colors.muted3 }}>
                    {al.detail}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </section>

      <section style={card}>
        <h2 style={{ ...sectionLabel, margin: '0 0 16px' }}>⚠ What this system does not know</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 11 }}>
          {unknowns.map((u) => (
            <div key={u} style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
              <span style={{ color: colors.muted, font: `500 11px/1.5 ${fonts.mono}`, flex: 'none' }}>—</span>
              <span style={{ font: `400 12px/1.5 ${fonts.sans}`, color: colors.text3 }}>{u}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}

// ---------------- view ----------------

export default function OverviewView({
  layers,
  marketState,
  assets,
  alerts,
  unknowns,
  sizingNote,
  kellyCap,
  selectedTicker,
  onSelectTicker,
}: {
  layers: Layer[]
  marketState: MarketState
  assets: Asset[]
  alerts: Alert[]
  unknowns: string[]
  sizingNote: string
  kellyCap: string
  selectedTicker: string
  onSelectTicker: (t: string) => void
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <GateStrip layers={layers} />
      <div style={{ display: 'grid', gridTemplateColumns: '1.45fr 1fr', gap: 18 }}>
        <MarketStatePanel marketState={marketState} />
        <SizingPanel assets={assets} selectedTicker={selectedTicker} sizingNote={sizingNote} kellyCap={kellyCap} />
      </div>
      <Watchlist assets={assets} selectedTicker={selectedTicker} onSelectTicker={onSelectTicker} />
      <AlertsAndUnknowns alerts={alerts} unknowns={unknowns} />
    </div>
  )
}
