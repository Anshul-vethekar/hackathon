import { useState, useEffect } from 'react'
import { api } from './api'
import BaselinePage from './pages/BaselinePage'
import DisruptionPage from './pages/DisruptionPage'
import RecoveryPage from './pages/RecoveryPage'
import MachinesPage from './pages/MachinesPage'

const PAGES = [
  { id: 'baseline',   label: 'Baseline Schedule', icon: '📊' },
  { id: 'disruption', label: 'Disruption Analysis', icon: '⚡' },
  { id: 'recovery',   label: 'Recovery Planner', icon: '🔄' },
  { id: 'machines',   label: 'Machine Fleet', icon: '🏭' },
]

export default function App() {
  const [page, setPage] = useState('baseline')
  const [online, setOnline] = useState(null)

  useEffect(() => {
    api.health()
      .then(() => setOnline(true))
      .catch(() => setOnline(false))
  }, [])

  const handleReset = async () => {
    await api.reset()
    window.location.reload()
  }

  return (
    <div className="app-shell">
      {/* Top bar */}
      <header className="topbar">
        <div className="topbar-brand">
          <div className="brand-icon">⟳</div>
          <span className="brand-name">Re<span>Flow</span></span>
        </div>
        <div className="topbar-status">
          <div className={`status-dot ${online === false ? 'offline' : ''}`} />
          {online === null ? 'Connecting…' : online ? 'API Connected' : 'API Offline'}
        </div>
        <div className="topbar-actions">
          <button className="btn btn-secondary btn-sm" onClick={handleReset} title="Reset baseline">
            ↺ Reset
          </button>
        </div>
      </header>

      {/* Sidebar */}
      <nav className="sidebar">
        <div className="sidebar-section-label">Navigation</div>
        {PAGES.map(p => (
          <div
            key={p.id}
            id={`nav-${p.id}`}
            className={`nav-item ${page === p.id ? 'active' : ''}`}
            onClick={() => setPage(p.id)}
          >
            <span className="icon">{p.icon}</span>
            {p.label}
          </div>
        ))}

        <div className="glow-divider" style={{ margin: '16px 0' }} />

        <div style={{ padding: '8px 12px', fontSize: '0.72rem', color: 'var(--text-muted)', lineHeight: 1.7 }}>
          <div style={{ fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 4 }}>ReFlow v1.0</div>
          Factory scheduling & disruption recovery engine.<br />
          Powered by heuristic constraint-satisfaction.
        </div>
      </nav>

      {/* Main content */}
      <main className="main-content">
        {page === 'baseline'   && <BaselinePage />}
        {page === 'disruption' && <DisruptionPage />}
        {page === 'recovery'   && <RecoveryPage />}
        {page === 'machines'   && <MachinesPage />}
      </main>
    </div>
  )
}
