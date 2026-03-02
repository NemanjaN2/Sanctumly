const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8080'

export async function uploadDocument(file, sessionId) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('session_id', sessionId)

  const response = await fetch(`${API_URL}/upload/document`, {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    throw new Error('Failed to upload document')
  }

  return response.json()
}

export async function getMemory(username) {
  const response = await fetch(`${API_URL}/memory/${username}`)
  
  if (!response.ok) {
    throw new Error('Failed to get memory')
  }

  return response.json()
}

export async function updateMemory(username, summary, keyFacts, preferences) {
  const response = await fetch(`${API_URL}/memory/update`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      username,
      summary,
      key_facts: keyFacts,
      preferences
    }),
  })

  if (!response.ok) {
    throw new Error('Failed to update memory')
  }

  return response.json()
}
