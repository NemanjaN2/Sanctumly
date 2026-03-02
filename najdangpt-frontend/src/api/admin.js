const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8080'

export async function getSettings() {
  const response = await fetch(`${API_URL}/admin/settings`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  })
  if (!response.ok) {
    throw new Error('Failed to fetch settings')
  }
  return response.json()
}

export async function saveSetting(key, value) {
  const response = await fetch(`${API_URL}/admin/settings?key=${encodeURIComponent(key)}&value=${encodeURIComponent(value)}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
  })
  if (!response.ok) {
    throw new Error('Failed to save setting')
  }
  return response.json()
}

// ===== Therapist Knowledge Base =====

export async function getTherapistKnowledge() {
  const res = await fetch(`${API_URL}/admin/therapist-knowledge`)
  if (!res.ok) throw new Error('Failed to load therapist knowledge')
  return res.json()
}

export async function createTherapistKnowledge(data) {
  const res = await fetch(`${API_URL}/admin/therapist-knowledge`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  })
  if (!res.ok) throw new Error('Failed to create entry')
  return res.json()
}

export async function updateTherapistKnowledge(id, data) {
  const res = await fetch(`${API_URL}/admin/therapist-knowledge/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  })
  if (!res.ok) throw new Error('Failed to update entry')
  return res.json()
}

export async function deleteTherapistKnowledge(id) {
  const res = await fetch(`${API_URL}/admin/therapist-knowledge/${id}`, {
    method: 'DELETE'
  })
  if (!res.ok) throw new Error('Failed to delete entry')
  return res.json()
}
