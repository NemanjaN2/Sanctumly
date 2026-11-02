import { authHeaders } from './chat'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'https://sanctumly-production.up.railway.app'

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      Accept: 'application/json',
      ...authHeaders(),
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...(options.headers || {}),
    },
    cache: 'no-store',
  })

  const raw = await response.text()
  let data = {}
  try { data = raw ? JSON.parse(raw) : {} }
  catch { data = { detail: raw.slice(0, 300) } }

  if (!response.ok) {
    const error = new Error(data.detail || `Request failed (${response.status})`)
    error.status = response.status
    throw error
  }

  return data
}

export function getAIControlOverview(days = 7) {
  return request(`/admin/ai-control/overview?days=${encodeURIComponent(days)}`)
}

export function updateAIProviderOverride(mode, durationMinutes = 60) {
  return request('/admin/ai-control/override', {
    method: 'PUT',
    body: JSON.stringify({ mode, duration_minutes: durationMinutes }),
  })
}
