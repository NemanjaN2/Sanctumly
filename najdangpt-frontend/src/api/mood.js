import { authHeaders } from './chat'

const API_URL = import.meta.env.VITE_API_URL || 'https://sanctumly-production.up.railway.app'

export async function moodCheckin(username, sessionId, moodScore, note = null) {
  const response = await fetch(`${API_URL}/mood/checkin`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({
      username,
      session_id: sessionId,
      mood_score: moodScore,
      note
    })
  })
  if (response.status === 401) throw new Error('Session expired — please log out and log in again')
  if (!response.ok) throw new Error('Failed to submit mood')
  return response.json()
}

export async function getMoodToday(username) {
  const response = await fetch(`${API_URL}/mood/today/${username}`, {
    headers: { ...authHeaders() }
  })
  if (response.status === 401) throw new Error('Session expired — please log out and log in again')
  if (!response.ok) throw new Error('Failed to check mood status')
  return response.json()
}

export async function getMoodHistory(username, days = 30) {
  const response = await fetch(`${API_URL}/mood/history/${username}?days=${days}`, {
    headers: { ...authHeaders() }
  })
  if (response.status === 401) throw new Error('Session expired — please log out and log in again')
  if (!response.ok) throw new Error('Failed to fetch mood history')
  return response.json()
}
