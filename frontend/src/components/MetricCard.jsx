export default function MetricCard({ label, value, sub, color = 'cyan' }) {
  return (
    <div className={`metric-card ${color}`}>
      <div className="metric-label">{label}</div>
      <div className={`metric-value ${color}`}>{value ?? '—'}</div>
      {sub && <div className="metric-sub">{sub}</div>}
    </div>
  )
}
