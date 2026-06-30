import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { colors, fonts } from './theme'
import { headers, type ViewId } from './data'
import {
  fetchDashboard,
  postJournalEntry,
  type DashboardData,
  type JournalEntryInput,
  type JournalSubmitResult,
} from './api'
import Sidebar from './components/Sidebar'
import Header from './components/Header'
import OverviewView from './views/OverviewView'
import PortfolioView from './views/PortfolioView'
import JournalView from './views/JournalView'
import CalibrationView from './views/CalibrationView'
import ValidationView from './views/ValidationView'

function CenterScreen({ children }: { children: ReactNode }) {
  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: colors.bg,
        padding: 24,
      }}
    >
      {children}
    </div>
  )
}

export default function App() {
  const [view, setView] = useState<ViewId>('overview')
  const [selectedTicker, setSelectedTicker] = useState('NVDA')
  const [stressScenario, setStressScenario] = useState('2022 Rate Shock')

  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchDashboard()
      .then((d) => {
        if (!cancelled) {
          setData(d)
          setLoading(false)
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : String(e))
          setLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [reloadKey])

  const handleJournalSubmit = useCallback(
    async (entry: JournalEntryInput): Promise<JournalSubmitResult> => {
      setSubmitting(true)
      try {
        const updated = await postJournalEntry(entry)
        setData(updated)
        return { ok: true }
      } catch (e) {
        return { ok: false, error: e instanceof Error ? e.message : String(e) }
      } finally {
        setSubmitting(false)
      }
    },
    [],
  )

  if (loading && !data) {
    return (
      <CenterScreen>
        <div style={{ textAlign: 'center', color: colors.text3, font: `400 14px/1.5 ${fonts.sans}` }}>
          <div
            style={{
              width: 26,
              height: 26,
              margin: '0 auto 16px',
              borderRadius: '50%',
              border: `2px solid ${colors.borderMid}`,
              borderTopColor: colors.blue,
              animation: 'spin .8s linear infinite',
            }}
          />
          Loading dashboard…
        </div>
      </CenterScreen>
    )
  }

  if (error && !data) {
    return (
      <CenterScreen>
        <div
          style={{
            maxWidth: 460,
            background: colors.card,
            border: `1px solid ${colors.border}`,
            borderRadius: 12,
            padding: '26px 28px',
            textAlign: 'center',
          }}
        >
          <div style={{ font: `600 15px/1.3 ${fonts.sans}`, color: colors.text, marginBottom: 10 }}>
            Couldn’t reach the dashboard API
          </div>
          <div style={{ font: `400 12px/1.5 ${fonts.mono}`, color: colors.red, marginBottom: 14 }}>{error}</div>
          <div style={{ font: `400 12px/1.5 ${fonts.sans}`, color: colors.text3, marginBottom: 18 }}>
            Start the backend with <code style={{ color: colors.text2 }}>python scripts/run_api.py</code> (port 8000),
            then retry.
          </div>
          <button
            onClick={() => setReloadKey((k) => k + 1)}
            style={{
              background: colors.blue,
              color: colors.sidebar,
              border: 'none',
              borderRadius: 8,
              padding: '9px 18px',
              font: `600 13px/1 ${fonts.sans}`,
              cursor: 'pointer',
            }}
          >
            Retry
          </button>
        </div>
      </CenterScreen>
    )
  }

  if (!data) return null

  const header = headers[view]

  return (
    <div style={{ display: 'flex', minHeight: '100vh', width: '100%', background: colors.bg }}>
      <Sidebar view={view} onNavigate={setView} asOf={data.meta.asOf} live={data.meta.live} />

      <main style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
        <Header header={header} gate={data.meta.gate} />

        <div
          key={view}
          style={{
            padding: '28px 34px 56px',
            display: 'flex',
            flexDirection: 'column',
            gap: 24,
            animation: 'fadein .22s ease',
          }}
        >
          {view === 'overview' && (
            <OverviewView
              layers={data.layers}
              marketState={data.marketState}
              assets={data.assets}
              alerts={data.alerts}
              unknowns={data.unknowns}
              sizingNote={data.sizingNote}
              kellyCap={data.meta.kellyCap}
              selectedTicker={selectedTicker}
              onSelectTicker={setSelectedTicker}
            />
          )}
          {view === 'portfolio' && (
            <PortfolioView portfolio={data.portfolio} scenario={stressScenario} onScenario={setStressScenario} />
          )}
          {view === 'journal' && (
            <JournalView journal={data.journal} submitting={submitting} onSubmit={handleJournalSubmit} />
          )}
          {view === 'calibration' && <CalibrationView calibration={data.calibration} />}
          {view === 'validation' && <ValidationView layers={data.layers} validation={data.validation} />}
        </div>
      </main>
    </div>
  )
}
