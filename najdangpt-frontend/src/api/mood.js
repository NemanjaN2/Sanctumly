const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8080'

export async function moodCheckin(username, sessionId, moodScore, note = null) {
  const response = await fetch(`${API_URL}/mood/checkin`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      username,
      session_id: sessionId,
      mood_score: moodScore,
      note
    })
  })
  if (!response.ok) throw new Error('Failed to submit mood')
  return response.json()
}

export async function getMoodToday(username) {
  const response = await fetch(`${API_URL}/mood/today/${username}`)
  if (!response.ok) throw new Error('Failed to check mood status')
  return response.json()
}

export async function getMoodHistory(username, days = 30) {
  const response = await fetch(`${API_URL}/mood/history/${username}?days=${days}`)
  if (!response.ok) throw new Error('Failed to fetch mood history')
  return response.json()
}
