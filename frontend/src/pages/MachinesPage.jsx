import { useBaseline } from '../hooks'
import { api } from '../api'

export default function MachinesPage() {
  const { data, loading, error } = useBaseline()

  if (loading) return <div className="loading-overlay"><div className="spinner" /><span>Loading…</span></div>
  if (error) return <div className="card"><div className="impact-alert-text">{error}</div></div>

  const { machines } = data

  return (
    <>
      <div className="page-header">
        <h1 className="page-title">Machine Fleet</h1>
        <div className="page-subtitle">Machine capacity, shift windows, and maintenance schedules</div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 16 }}>
        {machines.map(m => (
          <div className="card" key={m.id} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ fontWeight: 700, fontSize: '1rem' }}>{m.name}</div>
              <span className="badge badge-neutral cell-mono">{m.id}</span>
            </div>
            <div className="glow-divider" />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <div>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: 2 }}>SHIFT</div>
                <div className="cell-mono" style={{ fontSize: '0.85rem' }}>
                  {String(8 + Math.floor(m.shift_start / 60)).padStart(2,'0')}:{String(m.shift_start%60).padStart(2,'0')}
                  &nbsp;–&nbsp;
                  {String(8 + Math.floor(m.shift_end / 60)).padStart(2,'0')}:{String(m.shift_end%60).padStart(2,'0')}
                </div>
              </div>
              <div>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: 2 }}>MAINTENANCE</div>
                <div className="cell-mono" style={{ fontSize: '0.85rem', color: m.maint_start >= 0 ? 'var(--amber)' : 'var(--text-muted)' }}>
                  {m.maint_start >= 0 ? `${m.maint_start_clock} – ${m.maint_end_clock}` : 'None'}
                </div>
              </div>
            </div>
            <div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: 6 }}>SUPPORTED OPERATIONS</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {m.supported_operations.map(op => (
                  <span key={op} className="badge badge-medium">{op}</span>
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>
    </>
  )
}
