import { authHeaders } from './chat'

const API_URL = import.meta.env.VITE_API_URL || 'https://sanctumly-production.up.railway.app'

// Keep all administrative requests on the same server-issued Bearer session
// used by chat and the Creator AI Control Center.
function adminHeaders(includeJsonContentType = false) {
  return {
    Accept: 'application/json',
    ...authHeaders(),
    ...(includeJsonContentType ? { 'Content-Type': 'application/json' } : {}),
  }
}

async function readResponse(response, fallbackMessage) {
  const raw = await response.text()
  let data = {}
  try {
    data = raw ? JSON.parse(raw) : {}
  } catch {
    data = { detail: raw.slice(0, 300) }
  }

  if (!response.ok) {
    const error = new Error(data.detail || fallbackMessage || `Request failed (${response.status})`)
    error.status = response.status
    throw error
  }

  return data
}

export async function getSettings() {
  const response = await fetch(`${API_URL}/admin/settings`, {
    method: 'GET',
    headers: adminHeaders(),
    cache: 'no-store',
  })
  return readResponse(response, 'Failed to fetch settings')
}

export async function saveSetting(key, value) {
  const response = await fetch(`${API_URL}/admin/settings?key=${encodeURIComponent(key)}&value=${encodeURIComponent(value)}`, {
    method: 'POST',
    headers: adminHeaders(true),
  })
  return readResponse(response, 'Failed to save setting')
}

// ===== Therapist Knowledge Base =====

export async function getTherapistKnowledge() {
  const response = await fetch(`${API_URL}/admin/therapist-knowledge`, {
    method: 'GET',
    headers: adminHeaders(),
    cache: 'no-store',
  })
  return readResponse(response, 'Failed to load therapist knowledge')
}

export async function createTherapistKnowledge(data) {
  const response = await fetch(`${API_URL}/admin/therapist-knowledge`, {
    method: 'POST',
    headers: adminHeaders(true),
    body: JSON.stringify(data),
  })
  return readResponse(response, 'Failed to create entry')
}

export async function updateTherapistKnowledge(id, data) {
  const response = await fetch(`${API_URL}/admin/therapist-knowledge/${encodeURIComponent(id)}`, {
    method: 'PUT',
    headers: adminHeaders(true),
    body: JSON.stringify(data),
  })
  return readResponse(response, 'Failed to update entry')
}

export async function deleteTherapistKnowledge(id) {
  const response = await fetch(`${API_URL}/admin/therapist-knowledge/${encodeURIComponent(id)}`, {
    method: 'DELETE',
    headers: adminHeaders(),
  })
  return readResponse(response, 'Failed to delete entry')
}
