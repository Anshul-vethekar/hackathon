// Colour palette for Gantt bars — one per work-order, cycling
const WORK_ORDER_COLORS = [
  { bg: 'rgba(34,211,238,0.85)',  text: '#001f26' },
  { bg: 'rgba(167,139,250,0.85)', text: '#1a0a33' },
  { bg: 'rgba(52,211,153,0.85)',  text: '#002618' },
  { bg: 'rgba(251,191,36,0.85)',  text: '#2a1900' },
  { bg: 'rgba(248,113,113,0.85)', text: '#2a0000' },
  { bg: 'rgba(56,189,248,0.85)',  text: '#001a26' },
  { bg: 'rgba(249,115,22,0.85)',  text: '#2a0d00' },
  { bg: 'rgba(236,72,153,0.85)',  text: '#2a001a' },
]

export function getWorkOrderColor(woId, woColorMap) {
  if (!woColorMap.has(woId)) {
    woColorMap.set(woId, WORK_ORDER_COLORS[woColorMap.size % WORK_ORDER_COLORS.length])
  }
  return woColorMap.get(woId)
}

export function priorityBadge(priority) {
  switch ((priority || '').toLowerCase()) {
    case 'critical': return 'badge badge-critical'
    case 'high':     return 'badge badge-high'
    case 'medium':   return 'badge badge-medium'
    case 'low':      return 'badge badge-low'
    default:         return 'badge badge-neutral'
  }
}

export function statusBadgeClass(label) {
  switch ((label || '').toLowerCase()) {
    case 'moved & delayed': return 'badge badge-moved-delayed'
    case 'moved':           return 'badge badge-moved'
    case 'delayed':         return 'badge badge-delayed'
    case 'unaffected':      return 'badge badge-unaffected'
    default:                return 'badge badge-neutral'
  }
}

export function deltaClass(value) {
  if (value > 0) return 'delta delta-neg'
  if (value < 0) return 'delta delta-pos'
  return 'delta delta-neutral'
}

export function sign(value) {
  if (value > 0) return `+${value}`
  return `${value}`
}
