const BASE = '/api'

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`${res.status}: ${text}`)
  }
  return res.json()
}

export const api = {
  health: () => request('/health'),
  getBaseline: () => request('/baseline'),
  analyzeDisruption: (params) =>
    request('/disruption/analyze', { method: 'POST', body: JSON.stringify(params) }),
  scheduleRecovery: (params) =>
    request('/recovery/schedule', { method: 'POST', body: JSON.stringify(params) }),
  reset: () => request('/reset', { method: 'POST' }),
  exportCsv: (params) => {
    const q = new URLSearchParams(params).toString()
    window.open(`${BASE}/export?${q}`, '_blank')
  },
}
