import { useState } from 'react'
import { useDisruption } from '../hooks'
import { priorityBadge } from '../utils'

const DEFAULT_PARAMS = {
  machine_id: 'M1',
  breakdown_start: 60,
  breakdown_duration: 240,
  shipment_id: 'SHP-01',
  shipment_delay_duration: 180,
}

export default function DisruptionPage() {
  const [params, setParams] = useState(DEFAULT_PARAMS)
  const { result, loading, error, analyze } = useDisruption()

  const set = (k, v) => setParams(p => ({ ...p, [k]: v }))

  const handleAnalyze = () => analyze(params)

  return (
    <>
      <div className="page-header">
        <h1 className="page-title">Disruption Analysis</h1>
        <div className="page-subtitle">Simulate machine breakdowns and material shipment delays</div>
      </div>

      {/* Parameters */}
      <div className="card">
        <div className="card-header">
          <div className="card-title"><span className="icon">⚙️</span> Disruption Parameters</div>
        </div>
        <div className="form-grid">
          <div className="form-group">
            <label>Machine ID</label>
            <select value={params.machine_id} onChange={e => set('machine_id', e.target.value)}>
              {['M1','M2','M3','M4'].map(m => <option key={m}>{m}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label>Breakdown Start (min from 08:00)</label>
            <input type="number" min={0} max={540} value={params.breakdown_start}
              onChange={e => set('breakdown_start', Number(e.target.value))} />
          </div>
          <div className="form-group">
            <label>Breakdown Duration (min)</label>
            <input type="number" min={0} max={600} value={params.breakdown_duration}
              onChange={e => set('breakdown_duration', Number(e.target.value))} />
          </div>
          <div className="form-group">
            <label>Shipment ID</label>
            <select value={params.shipment_id} onChange={e => set('shipment_id', e.target.value)}>
              {['SHP-01'].map(s => <option key={s}>{s}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label>Shipment Delay (min)</label>
            <input type="number" min={0} max={600} value={params.shipment_delay_duration}
              onChange={e => set('shipment_delay_duration', Number(e.target.value))} />
          </div>
        </div>
        <div style={{ marginTop: 16, display: 'flex', gap: 10 }}>
          <button id="btn-analyze-disruption" className="btn btn-primary" onClick={handleAnalyze} disabled={loading}>
            {loading ? '⏳ Analysing…' : '🔍 Analyse Impact'}
          </button>
          <button className="btn btn-secondary" onClick={() => setParams(DEFAULT_PARAMS)}>Reset</button>
        </div>
      </div>

      {error && (
        <div className="impact-alert">
          <div className="impact-alert-icon">⚠️</div>
          <div className="impact-alert-body">
            <div className="impact-alert-title">Error</div>
            <div className="impact-alert-text">{error}</div>
          </div>
        </div>
      )}

      {result && (
        <>
          {/* Narrative */}
          <div className="impact-alert">
            <div className="impact-alert-icon">🚨</div>
            <div className="impact-alert-body">
              <div className="impact-alert-title">Impact Summary</div>
              <div className="impact-alert-text">{result.summary_narrative}</div>
            </div>
          </div>

          {/* Affected counts */}
          <div className="metric-grid">
            <div className="metric-card rose">
              <div className="metric-label">Directly Affected Ops</div>
              <div className="metric-value rose">{result.directly_affected_op_ids.length}</div>
            </div>
            <div className="metric-card amber">
              <div className="metric-label">Downstream Affected</div>
              <div className="metric-value amber">{result.downstream_affected_op_ids.length}</div>
            </div>
            <div className="metric-card emerald">
              <div className="metric-label">Unaffected Ops</div>
              <div className="metric-value emerald">{result.unaffected_op_ids.length}</div>
            </div>
            <div className="metric-card violet">
              <div className="metric-label">WOs at Deadline Risk</div>
              <div className="metric-value violet">{result.work_orders_at_deadline_risk.length}</div>
            </div>
          </div>

          {/* Operations impact table */}
          <div className="card">
            <div className="card-header">
              <div className="card-title"><span className="icon">⚡</span> Operation Impacts</div>
              <span className="badge badge-error">{result.operation_impacts.length} affected</span>
            </div>
            <div className="table-wrapper">
              <table>
                <thead>
                  <tr>
                    <th>Op ID</th>
                    <th>WO</th>
                    <th>Stage</th>
                    <th>Machine</th>
                    <th>Baseline Start</th>
                    <th>Baseline Finish</th>
                    <th>Cause</th>
                    <th>Risk</th>
                  </tr>
                </thead>
                <tbody>
                  {result.operation_impacts.map(op => (
                    <tr key={op.operation_id}>
                      <td className="cell-mono">{op.operation_id}</td>
                      <td className="cell-mono">{op.work_order_id}</td>
                      <td>{op.stage_name}</td>
                      <td className="cell-mono">{op.assigned_machine}</td>
                      <td className="cell-mono">{op.baseline_start_clock}</td>
                      <td className="cell-mono">{op.baseline_finish_clock}</td>
                      <td style={{ maxWidth: 200, fontSize: '0.78rem' }}>{op.detail}</td>
                      <td>
                        <span className={op.deadline_risk ? 'badge badge-error' : 'badge badge-ok'}>
                          {op.deadline_risk ? '⚠ At Risk' : 'OK'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </>
  )
}
