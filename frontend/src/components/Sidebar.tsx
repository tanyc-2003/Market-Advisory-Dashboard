import { useState } from 'react'
import { colors, fonts } from '../theme'
import { navItems, type NavItem, type ViewId } from '../data'

interface SidebarProps {
  view: ViewId
  onNavigate: (v: ViewId) => void
  asOf: string
  live: boolean
}

function NavRow({
  item,
  active,
  onNavigate,
}: {
  item: NavItem
  active: boolean
  onNavigate: (v: ViewId) => void
}) {
  const [hover, setHover] = useState(false)
  const hov = !item.disabled && !active && hover

  return (
    <div
      title={item.title ?? ''}
      onClick={() => {
        if (!item.disabled) onNavigate(item.id as ViewId)
      }}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 11,
        padding: '10px 12px',
        borderRadius: 8,
        font: `500 13px/1 ${fonts.sans}`,
        cursor: item.disabled ? 'not-allowed' : 'pointer',
        transition: 'background .12s',
        background: active ? colors.navActive : hov ? colors.card : 'transparent',
        color: item.disabled
          ? colors.navDisabled
          : active
            ? colors.textNav
            : hov
              ? colors.text2
              : colors.text3,
        opacity: item.disabled ? 0.5 : 1,
      }}
    >
      <span
        style={{
          width: 6,
          height: 6,
          borderRadius: '50%',
          flex: 'none',
          background: active ? colors.blue : colors.dim,
        }}
      />
      <span style={{ flex: 1 }}>{item.label}</span>
      {item.tag && (
        <span
          style={{
            font: `500 9px/1 ${fonts.mono}`,
            color: colors.muted,
            border: `1px solid ${colors.border}`,
            borderRadius: 4,
            padding: '3px 5px',
            letterSpacing: '0.06em',
          }}
        >
          {item.tag}
        </span>
      )}
    </div>
  )
}

export default function Sidebar({ view, onNavigate, asOf, live }: SidebarProps) {
  return (
    <aside
      style={{
        width: 248,
        flex: 'none',
        background: colors.sidebar,
        borderRight: `1px solid ${colors.borderSoft}`,
        display: 'flex',
        flexDirection: 'column',
        position: 'sticky',
        top: 0,
        height: '100vh',
      }}
    >
      {/* brand */}
      <div style={{ padding: '22px 22px 18px', borderBottom: `1px solid ${colors.borderSoft}` }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div
            style={{
              width: 26,
              height: 26,
              borderRadius: 6,
              background: colors.blue,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              font: `700 13px/1 ${fonts.mono}`,
              color: colors.sidebar,
            }}
          >
            MA
          </div>
          <div>
            <div style={{ font: `600 14px/1.1 ${fonts.sans}`, letterSpacing: '-0.01em' }}>
              Market Advisory
            </div>
            <div style={{ font: `400 10px/1.3 ${fonts.mono}`, color: colors.muted, letterSpacing: '0.04em' }}>
              EVIDENCE-GATED · v7-lite
            </div>
          </div>
        </div>
      </div>

      {/* nav */}
      <nav style={{ padding: '14px 12px', display: 'flex', flexDirection: 'column', gap: 2 }}>
        {navItems.map((item, i) => (
          <NavRow
            key={`${item.id}-${i}`}
            item={item}
            active={!item.disabled && item.id === view}
            onNavigate={onNavigate}
          />
        ))}
      </nav>

      {/* snapshot */}
      <div style={{ marginTop: 'auto', padding: '16px 18px', borderTop: `1px solid ${colors.borderSoft}` }}>
        <div
          style={{
            font: `500 10px/1 ${fonts.mono}`,
            color: colors.muted,
            letterSpacing: '0.1em',
            textTransform: 'uppercase',
            marginBottom: 8,
          }}
        >
          Snapshot
        </div>
        <div style={{ font: `500 13px/1.2 ${fonts.mono}`, color: colors.text }}>{asOf}</div>
        <div
          style={{
            marginTop: 12,
            display: 'flex',
            alignItems: 'flex-start',
            gap: 8,
            padding: '9px 10px',
            borderRadius: 7,
            background: 'rgba(224,176,74,0.09)',
            border: '1px solid rgba(224,176,74,0.28)',
          }}
        >
          <span style={{ color: colors.amber, fontSize: 12, lineHeight: 1.5 }}>▲</span>
          <span style={{ font: `400 11px/1.45 ${fonts.sans}`, color: colors.amberText }}>
            {live
              ? 'Data is current. Outputs reflect the most recent point-in-time feature snapshot.'
              : 'Representative data — backend store not seeded. Log a trade to start a live journal.'}
          </span>
        </div>
      </div>
    </aside>
  )
}
