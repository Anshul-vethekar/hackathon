import { useState, useRef } from 'react'
import { getWorkOrderColor } from '../utils'

// Shift window: 0–600 minutes (08:00–18:00)
const SHIFT_START = 0
const SHIFT_END   = 600

function timeToPercent(t) {
  return ((t - SHIFT_START) / (SHIFT_END - SHIFT_START)) * 100
}

function durationToPercent(d) {
  return (d / (SHIFT_END - SHIFT_START)) * 100
}

const TIME_TICKS = [0, 60, 120, 180, 240, 300, 360, 420, 480, 540, 600]
const minutesToClock = (m) => {
  const total = 8 * 60 + m
  const h = Math.floor(total / 60) % 24
  const min = total % 60
  return `${String(h).padStart(2, '0')}:${String(min).padStart(2, '0')}`
}

export default function GanttChart({ schedule, machines, disruption }) {
  const [tooltip, setTooltip] = useState(null)
  const woColorMap = useRef(new Map())

  // Group by machine
  const byMachine = {}
  for (const m of machines) {
    byMachine[m.id] = { machine: m, bars: [] }
  }
  for (const item of schedule) {
    const machineId = item.assigned_machine || item.original_machine
    if (!byMachine[machineId]) byMachine[machineId] = { machine: { id: machineId, name: machineId }, bars: [] }
    byMachine[machineId].bars.push(item)
  }

  return (
    <div className="gantt-wrapper">
      <div className="gantt-chart">
        {/* Time axis */}
        <div className="gantt-time-labels" style={{ paddingLeft: '150px' }}>
          {TIME_TICKS.map(t => (
            <span key={t}>{minutesToClock(t)}</span>
          ))}
        </div>

        {Object.values(byMachine).map(({ machine, bars }) => (
          <div className="gantt-row" key={machine.id}>
            <div className="gantt-machine-label" style={{ width: '150px' }}>
              {machine.name || machine.id}
            </div>
            <div className="gantt-track">
              {/* Maintenance block */}
              {machine.maint_start != null && machine.maint_start >= 0 && (
                <div
                  className="gantt-maint-block"
                  style={{
                    left: `${timeToPercent(machine.maint_start)}%`,
                    width: `${durationToPercent(machine.maint_end - machine.maint_start)}%`,
                  }}
                  title={`Maintenance: ${minutesToClock(machine.maint_start)}–${minutesToClock(machine.maint_end)}`}
                />
              )}

              {/* Disruption breakdown window */}
              {disruption && machine.id === disruption.machine_id && (
                <div
                  style={{
                    position: 'absolute',
                    left: `${timeToPercent(disruption.breakdown_start)}%`,
                    width: `${durationToPercent(disruption.breakdown_duration)}%`,
                    height: '100%',
                    background: 'repeating-linear-gradient(135deg, rgba(248,113,113,0.18), rgba(248,113,113,0.18) 4px, transparent 4px, transparent 8px)',
                    borderRadius: '4px',
                    border: '1px solid rgba(248,113,113,0.4)',
                    zIndex: 1,
                  }}
                  title={`Breakdown: ${minutesToClock(disruption.breakdown_start)}–${minutesToClock(disruption.breakdown_start + disruption.breakdown_duration)}`}
                />
              )}

              {/* Bars */}
              {bars.map((item, idx) => {
                const startKey = item.start_time ?? item.original_start ?? 0
                const finishKey = item.finish_time ?? item.original_finish ?? 0
                const col = getWorkOrderColor(item.work_order_id, woColorMap.current)
                const left = timeToPercent(startKey)
                const width = durationToPercent(finishKey - startKey)
                const barId = `${item.operation_id}-${idx}`
                return (
                  <div
                    key={barId}
                    id={`gantt-bar-${barId}`}
                    className="gantt-bar"
                    style={{
                      left: `${left}%`,
                      width: `${Math.max(width, 0.5)}%`,
                      backgroundColor: col.bg,
                      color: col.text,
                    }}
                    onMouseEnter={(e) => setTooltip({ item, rect: e.currentTarget.getBoundingClientRect() })}
                    onMouseLeave={() => setTooltip(null)}
                  >
                    <span className="gantt-bar-label">
                      {item.operation_id}
                    </span>

                    {tooltip?.item === item && (
                      <div className="gantt-tooltip">
                        <strong>{item.operation_id}</strong> — {item.stage_name}<br />
                        WO: {item.work_order_id} · {item.customer}<br />
                        Priority: {item.priority}<br />
                        {item.start_clock ?? item.original_start_clock} → {item.finish_clock ?? item.original_finish_clock}<br />
                        Due: {item.due_clock}
                        {item.status_label && <><br /><span>Status: {item.status_label}</span></>}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
