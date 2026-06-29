import { useState } from 'react'
import { colors } from './theme'
import { headers, type ViewId } from './data'
import Sidebar from './components/Sidebar'
import Header from './components/Header'
import OverviewView from './views/OverviewView'
import PortfolioView from './views/PortfolioView'
import JournalView from './views/JournalView'
import CalibrationView from './views/CalibrationView'
import ValidationView from './views/ValidationView'

export default function App() {
  const [view, setView] = useState<ViewId>('overview')
  const [selectedTicker, setSelectedTicker] = useState('NVDA')
  const [stressScenario, setStressScenario] = useState('2022 Rate Shock')

  const header = headers[view]

  return (
    <div style={{ display: 'flex', minHeight: '100vh', width: '100%', background: colors.bg }}>
      <Sidebar view={view} onNavigate={setView} />

      <main style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
        <Header header={header} />

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
            <OverviewView selectedTicker={selectedTicker} onSelectTicker={setSelectedTicker} />
          )}
          {view === 'portfolio' && (
            <PortfolioView scenario={stressScenario} onScenario={setStressScenario} />
          )}
          {view === 'journal' && <JournalView />}
          {view === 'calibration' && <CalibrationView />}
          {view === 'validation' && <ValidationView />}
        </div>
      </main>
    </div>
  )
}
