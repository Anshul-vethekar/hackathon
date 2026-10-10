import { useBaseline } from '../hooks'
import MetricCard from '../components/MetricCard'
import GanttChart from '../components/GanttChart'
import { priorityBadge } from '../utils'

export default function BaselinePage() {
  const { data, loading, error, refetch } = useBaseline()

  if (loading) return (
    <div className="loading-overlay">
      <div className="spinner" />
      <span>Loading baseline schedule…</span>
    </div>
  )

  if (error) return (
    <div className="card">
      <div className="impact-alert">
        <div className="impact-alert-icon">⚠️</div>
        <div className="impact-alert-body">
          <div className="impact-alert-title">Failed to load baseline</div>
          <div className="impact-alert-text">{error}</div>
        </div>
      </div>
      <button className="btn btn-secondary" style={{ marginTop: 14 }} onClick={refetch}>Retry</button>
    </div>
  )

  const { metrics, schedule, machines, work_orders } = data

  return (
    <>
      <div className="page-header">
        <h1 className="page-title">Baseline Schedule</h1>
        <div className="page-subtitle">Optimal production plan before any disruptions</div>
      </div>

      {/* KPI row */}
      <div className="metric-grid">
        <MetricCard label="Work Orders" value={metrics.total_work_orders} color="cyan" />
        <MetricCard label="Completed" value={metrics.completed_work_orders} color="emerald" />
        <MetricCard label="Late" value={metrics.late_work_orders} color="rose" />
        <MetricCard label="Total Tardiness" value={`${metrics.total_tardiness_hours.toFixed(1)}h`} color="amber" />
        <MetricCard label="Utilisation" value={`${metrics.machine_utilization_pct.toFixed(1)}%`} color="violet" />
        <MetricCard label="Changeovers" value={metrics.number_of_changeovers} color="sky" />
        <MetricCard label="Idle Hours" value={`${metrics.machine_idle_hours.toFixed(1)}h`} color="sky" />
        <MetricCard label="Validation"
          value={metrics.validation_status === 'PASS' ? '✓ PASS' : '✗ FAIL'}
          color={metrics.validation_status === 'PASS' ? 'emerald' : 'rose'}
        />
      </div>

      {/* Gantt */}
      <div className="card">
        <div className="card-header">
          <div className="card-title"><span className="icon">📊</span> Machine Timeline</div>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>08:00 – 18:00</span>
        </div>
        <GanttChart schedule={schedule} machines={machines} />
      </div>

      {/* Work Orders table */}
      <div className="card">
        <div className="card-header">
          <div className="card-title"><span className="icon">📋</span> Work Orders</div>
          <span className="badge badge-neutral">{work_orders.length} orders</span>
        </div>
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Order ID</th>
                <th>Customer</th>
                <th>Priority</th>
                <th>Release</th>
                <th>Due</th>
              </tr>
            </thead>
            <tbody>
              {work_orders.map(wo => (
                <tr key={wo.id}>
                  <td className="cell-mono">{wo.id}</td>
                  <td>{wo.customer}</td>
                  <td><span className={priorityBadge(wo.priority)}>{wo.priority}</span></td>
                  <td className="cell-mono">{wo.release_clock}</td>
                  <td className="cell-mono">{wo.due_clock}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Schedule details table */}
      <div className="card">
        <div className="card-header">
          <div className="card-title"><span className="icon">🔧</span> Operation Schedule</div>
          <span className="badge badge-neutral">{schedule.length} ops</span>
        </div>
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Op ID</th>
                <th>WO</th>
                <th>Stage</th>
                <th>Machine</th>
                <th>Priority</th>
                <th>Start</th>
                <th>Finish</th>
                <th>Due</th>
              </tr>
            </thead>
            <tbody>
              {schedule.map(op => (
                <tr key={op.operation_id}>
                  <td className="cell-mono">{op.operation_id}</td>
                  <td className="cell-mono">{op.work_order_id}</td>
                  <td>{op.stage_name}</td>
                  <td className="cell-mono">{op.assigned_machine}</td>
                  <td><span className={priorityBadge(op.priority)}>{op.priority}</span></td>
                  <td className="cell-mono">{op.start_clock}</td>
                  <td className="cell-mono">{op.finish_clock}</td>
                  <td className="cell-mono">{op.due_clock}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  )
}
