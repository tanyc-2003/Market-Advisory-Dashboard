import { colors, fonts } from '../theme'
import { gateCounts, type HeaderInfo } from '../data'

function GatePill({ color, label }: { color: string; label: string }) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 7,
        padding: '8px 12px',
        borderRadius: 8,
        background: colors.card,
        border: `1px solid ${colors.border}`,
      }}
    >
      <span style={{ width: 7, height: 7, borderRadius: '50%', background: color }} />
      <span style={{ font: `500 12px/1 ${fonts.mono}`, color: colors.text2 }}>{label}</span>
    </div>
  )
}

export default function Header({ header }: { header: HeaderInfo }) {
  return (
    <header
      style={{
        padding: '24px 34px 20px',
        borderBottom: `1px solid ${colors.borderSoft}`,
        display: 'flex',
        alignItems: 'flex-end',
        justifyContent: 'space-between',
        gap: 24,
        position: 'sticky',
        top: 0,
        background: 'rgba(16,19,25,0.86)',
        backdropFilter: 'blur(8px)',
        WebkitBackdropFilter: 'blur(8px)',
        zIndex: 5,
      }}
    >
      <div>
        <div
          style={{
            font: `500 11px/1 ${fonts.mono}`,
            color: colors.muted,
            letterSpacing: '0.12em',
            textTransform: 'uppercase',
            marginBottom: 9,
          }}
        >
          {header.kicker}
        </div>
        <h1 style={{ margin: 0, font: `600 26px/1.1 ${fonts.sans}`, letterSpacing: '-0.02em' }}>
          {header.title}
        </h1>
        <p style={{ margin: '7px 0 0', font: `400 13px/1.45 ${fonts.sans}`, color: colors.text3, maxWidth: 560 }}>
          {header.subtitle}
        </p>
      </div>
      <div style={{ flex: 'none', display: 'flex', gap: 8, alignItems: 'center' }}>
        <GatePill color={colors.green} label={`${gateCounts.production} production`} />
        <GatePill color={colors.amber} label={`${gateCounts.preview} preview`} />
      </div>
    </header>
  )
}
