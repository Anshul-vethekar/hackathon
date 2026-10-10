import { useState } from 'react'
import { useBaseline, useRecovery } from '../hooks'
import { api } from '../api'
import MetricCard from '../components/MetricCard'
import GanttChart from '../components/GanttChart'
import { statusBadgeClass, deltaClass, sign, priorityBadge } from '../utils'

const STRATEGIES = [
  {
    id: 'PLAN_A',
    title: 'Plan A — Resequence',
    desc: 'Resequence unaffected operations to maintain throughput. Minimal disruption to overall schedule.',
  },
  {
    id: 'PLAN_B',
    title: 'Plan B — Reassign Machines',
    desc: 'Shift blocked operations to alternative compatible machines to bypass the breakdown.',
  },
  {
    id: 'PLAN_C',
    title: 'Plan C — Priority-first',
    desc: 'Prioritise critical and high-priority work orders. Defer low-priority operations if necessary.',
  },
]

const DEFAULT_DISRUPTION = {
  machine_id: 'M1',
  breakdown_start: 60,
  breakdown_duration: 240,
  shipment_id: 'SHP-01',
  shipment_delay_duration: 180,
}

const TAB_IDS = ['schedule', 'metrics', 'validation', 'trace']

export default function RecoveryPage() {
  const [disruption, setDisruption] = useState(DEFAULT_DISRUPTION)
  const [strategy, setStrategy] = useState('PLAN_A')
  const [activeTab, setActiveTab] = useState('schedule')
  const { data: baseline } = useBaseline()
  const { result, loading, error, run } = useRecovery()

  const setDis = (k, v) => setDisruption(p => ({ ...p, [k]: v }))

  const handleRun = () => run({ strategy, disruption })

  const handleExport = () => api.exportCsv({
    strategy,
    ...disruption,
  })

  return (
    <>
      <div className="page-header">
        <h1 className="page-title">Recovery Planner</h1>
        <div className="page-subtitle">Generate and compare recovery schedules across strategies</div>
      </div>

      {/* Disruption config */}
      <div className="card">
        <div className="card-header">
          <div className="card-title"><span className="icon">⚙️</span> Disruption Configuration</div>
        </div>
        <div className="form-grid">
          <div className="form-group">
            <label>Machine ID</label>
            <select value={disruption.machine_id} onChange={e => setDis('machine_id', e.target.value)}>
              {['M1','M2','M3','M4'].map(m => <option key={m}>{m}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label>Breakdown Start (min)</label>
            <input type="number" min={0} max={540} value={disruption.breakdown_start}
              onChange={e => setDis('breakdown_start', Number(e.target.value))} />
          </div>
          <div className="form-group">
            <label>Breakdown Duration (min)</label>
            <input type="number" min={0} max={600} value={disruption.breakdown_duration}
              onChange={e => setDis('breakdown_duration', Number(e.target.value))} />
          </div>
          <div className="form-group">
            <label>Shipment ID</label>
            <select value={disruption.shipment_id} onChange={e => setDis('shipment_id', e.target.value)}>
              {['SHP-01'].map(s => <option key={s}>{s}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label>Shipment Delay (min)</label>
            <input type="number" min={0} max={600} value={disruption.shipment_delay_duration}
              onChange={e => setDis('shipment_delay_duration', Number(e.target.value))} />
          </div>
        </div>
      </div>

      {/* Strategy selector */}
      <div className="card">
        <div className="card-header">
          <div className="card-title"><span className="icon">🎯</span> Recovery Strategy</div>
        </div>
        <div className="strategy-grid">
          {STRATEGIES.map(s => (
            <div
              key={s.id}
              id={`strategy-${s.id.toLowerCase()}`}
              className={`strategy-card ${strategy === s.id ? 'selected' : ''}`}
              onClick={() => setStrategy(s.id)}
            >
              <div className="strategy-card-title">{s.title}</div>
              <div className="strategy-card-desc">{s.desc}</div>
            </div>
          ))}
        </div>
        <div style={{ marginTop: 16, display: 'flex', gap: 10 }}>
          <button id="btn-run-recovery" className="btn btn-primary" onClick={handleRun} disabled={loading}>
            {loading ? '⏳ Running…' : '🚀 Generate Recovery Schedule'}
          </button>
          {result && (
            <button className="btn btn-secondary" onClick={handleExport}>
              ⬇ Export CSV
            </button>
          )}
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
          {/* Comparison KPIs */}
          <div className="card">
            <div className="card-header">
              <div className="card-title"><span className="icon">📈</span> vs Baseline Comparison</div>
              <span className="badge badge-neutral">{result.strategy_name}</span>
            </div>
            <div className="metric-grid">
              <MetricCard label="Tardiness" value={`${result.metrics.total_tardiness_hours.toFixed(1)}h`} color="amber" sub={
                <span className={deltaClass(result.comparison.tardiness_delta_hours)}>
                  {sign(result.comparison.tardiness_delta_hours.toFixed(1))}h vs baseline
                </span>
              } />
              <MetricCard label="Late Orders" value={result.metrics.late_work_orders} color="rose" sub={
                <span className={deltaClass(result.comparison.late_orders_delta)}>
                  {sign(result.comparison.late_orders_delta)} vs baseline
                </span>
              } />
              <MetricCard label="Critical Late" value={result.metrics.critical_orders_late} color="rose" sub={
                <span className={deltaClass(result.comparison.critical_late_delta)}>
                  {sign(result.comparison.critical_late_delta)}
                </span>
              } />
              <MetricCard label="Utilisation" value={`${result.metrics.machine_utilization_pct.toFixed(1)}%`} color="violet" sub={
                <span className={deltaClass(-result.comparison.utilization_delta_pct)}>
                  {sign(result.comparison.utilization_delta_pct.toFixed(1))}%
                </span>
              } />
              <MetricCard label="Moved Ops" value={result.comparison.moved_ops_count} color="sky" />
              <MetricCard label="Delayed Ops" value={result.comparison.delayed_ops_count} color="amber" />
              <MetricCard label="Validation"
                value={result.validation.is_feasible ? '✓ PASS' : '✗ FAIL'}
                color={result.validation.is_feasible ? 'emerald' : 'rose'}
              />
              <MetricCard label="Unscheduled" value={result.metrics.unscheduled_operations} color="rose" />
            </div>
            {result.comparison.tradeoff_summary && (
              <div style={{ marginTop: 14, padding: '12px 16px', background: 'var(--bg-card2)', borderRadius: 'var(--radius-sm)', fontSize: '0.83rem', color: 'var(--text-secondary)', lineHeight: 1.7 }}>
                💡 {result.comparison.tradeoff_summary}
              </div>
            )}
          </div>

          {/* Tabs */}
          <div className="card">
            <div className="tabs">
              {TAB_IDS.map(t => (
                <div key={t} className={`tab ${activeTab === t ? 'active' : ''}`} onClick={() => setActiveTab(t)}>
                  {{ schedule: '📊 Gantt', metrics: '📋 Schedule Table', validation: '✅ Validation', trace: '🔍 Decision Trace' }[t]}
                </div>
              ))}
            </div>

            {activeTab === 'schedule' && baseline && (
              <GanttChart
                schedule={result.schedule}
                machines={baseline.machines}
                disruption={{ ...disruption }}
              />
            )}

            {activeTab === 'metrics' && (
              <div className="table-wrapper">
                <table>
                  <thead>
                    <tr>
                      <th>Op ID</th>
                      <th>WO</th>
                      <th>Stage</th>
                      <th>Machine</th>
                      <th>Priority</th>
                      <th>Orig Start</th>
                      <th>New Start</th>
                      <th>New Finish</th>
                      <th>Due</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.schedule.map(op => (
                      <tr key={op.operation_id}>
                        <td className="cell-mono">{op.operation_id}</td>
                        <td className="cell-mono">{op.work_order_id}</td>
                        <td>{op.stage_name}</td>
                        <td className="cell-mono">
                          {op.assigned_machine}
                          {op.assigned_machine !== op.original_machine && (
                            <span style={{ marginLeft: 6, fontSize: '0.7rem', color: 'var(--violet)' }}>
                              (was {op.original_machine})
                            </span>
                          )}
                        </td>
                        <td><span className={priorityBadge(op.priority)}>{op.priority}</span></td>
                        <td className="cell-mono">{op.original_start_clock}</td>
                        <td className="cell-mono">{op.start_clock}</td>
                        <td className="cell-mono">{op.finish_clock}</td>
                        <td className="cell-mono">{op.due_clock}</td>
                        <td><span className={statusBadgeClass(op.status_label)}>{op.status_label}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {activeTab === 'validation' && (
              <div className="validation-checks">
                {result.validation.checks.map((c, i) => (
                  <div key={i} className={`check-item check-${c.status.toLowerCase() === 'pass' ? 'pass' : c.status.toLowerCase() === 'warn' ? 'warn' : 'fail'}`}>
                    <div className="check-icon">
                      {c.status === 'PASS' ? '✅' : c.status === 'WARN' ? '⚠️' : '❌'}
                    </div>
                    <div className="check-body">
                      <div className="check-title">Rule {c.rule_number}: {c.rule_name}</div>
                      <div className="check-msg">{c.message}</div>
                      {c.details && c.details.length > 0 && (
                        <div style={{ marginTop: 6, fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          {c.details.map((d, di) => <div key={di}>• {d}</div>)}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {activeTab === 'trace' && (
              <div>
                {result.decision_trace.map((t) => (
                  <div key={t.step_id} className="trace-step">
                    <div className="trace-step-header">
                      <span className="trace-step-id">#{t.step_id}</span>
                      <span className="trace-step-op">{t.operation_id}</span>
                      <span className="badge badge-neutral">{t.work_order_id}</span>
                      <span className={`badge ${priorityBadge(t.priority)}`}>{t.priority}</span>
                      {t.selected_machine && (
                        <span className="badge badge-ok">→ {t.selected_machine}</span>
                      )}
                      {t.scheduled_start_clock && (
                        <span className="cell-mono" style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                          {t.scheduled_start_clock} – {t.scheduled_finish_clock}
                        </span>
                      )}
                    </div>
                    <div className="trace-step-narrative">{t.decision_narrative}</div>
                    {t.rejected_reasons && t.rejected_reasons.length > 0 && (
                      <div className="trace-rejected">
                        <span style={{ color: 'var(--text-muted)', marginRight: 4 }}>Rejected:</span>
                        {t.rejected_reasons.map((r, ri) => (
                          <span key={ri} className="trace-rejected-item">{r}</span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </>
  )
}
