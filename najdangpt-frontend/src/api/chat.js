const API_BASE_URL = import.meta.env.VITE_API_URL || 'https://sanctumly-production.up.railway.app'

// ── Auth ─────────────────────────────────────────────────────────────
// Backend v8 gates protected routes behind require_user, which validates
// the SERVER-issued login session (session_<user>_<ts>_<random>) sent as
// a Bearer token. This is stored separately from the chat session_id,
// because ChatPage generates local chat session ids that are NOT valid
// auth tokens.
const AUTH_KEY = 'sanctumly_auth_token'

export function setAuthToken(token) {
  if (token) localStorage.setItem(AUTH_KEY, token)
}

export function clearAuthToken() {
  localStorage.removeItem(AUTH_KEY)
}

export function authHeaders() {
  const t = localStorage.getItem(AUTH_KEY)
  return t ? { 'Authorization': `Bearer ${t}` } : {}
}
// ─────────────────────────────────────────────────────────────────────

export async function sendMessage(message, sessionId, username, personality = 'default', image = null) {
  try {
    const body = { message, session_id: sessionId, username, personality }
    if (image) body.image = image
    const response = await fetch(`${API_BASE_URL}/chat/message`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify(body),
    })
    if (response.status === 401) throw new Error('Session expired — please log out and log in again')
    if (!response.ok) throw new Error('Failed to send message')
    return await response.json()
  } catch (error) {
    console.error('Error sending message:', error)
    throw error
  }
}

// Streams the assistant reply token-by-token via onToken(text).
// Falls back to the non-streaming endpoint if /chat/stream isn't available.
export async function streamMessage(message, sessionId, username, personality = 'default', onToken) {
  const body = JSON.stringify({ message, session_id: sessionId, username, personality })

  let response
  try {
    response = await fetch(`${API_BASE_URL}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body,
    })
  } catch (err) {
    // Network-level failure — try the normal endpoint once
    const data = await sendMessage(message, sessionId, username, personality)
    onToken(data.response || '')
    return
  }

  // Backend has no streaming endpoint → fall back
  if (!response.ok || !response.body) {
    const data = await sendMessage(message, sessionId, username, personality)
    onToken(data.response || '')
    return
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let receivedAny = false

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      // SSE format: lines starting with "data:"
      if (buffer.includes('data:')) {
        const lines = buffer.split('\n')
        buffer = lines.pop() || '' // keep incomplete last line
        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed.startsWith('data:')) continue
          const payload = trimmed.slice(5).trim()
          if (!payload || payload === '[DONE]') continue
          let text = payload
          try {
            const parsed = JSON.parse(payload)
            text = parsed.token ?? parsed.content ?? parsed.response ?? parsed.text ?? ''
          } catch { /* plain text payload */ }
          if (text) { receivedAny = true; onToken(text) }
        }
      } else {
        // Plain chunked text — flush as-is
        if (buffer) { receivedAny = true; onToken(buffer); buffer = '' }
      }
    }
    // Flush any trailing plain-text buffer
    if (buffer && !buffer.trim().startsWith('data:')) onToken(buffer)
  } catch (err) {
    if (!receivedAny) {
      const data = await sendMessage(message, sessionId, username, personality)
      onToken(data.response || '')
      return
    }
    console.error('Stream interrupted:', err)
    throw err
  }
}

export async function clearChat(sessionId) {
  try {
    const response = await fetch(`${API_BASE_URL}/chat/clear/${sessionId}`, {
      method: 'DELETE',
      headers: { ...authHeaders() },
    })
    if (!response.ok) throw new Error('Failed to clear chat')
    return await response.json()
  } catch (error) {
    console.error('Error clearing chat:', error)
    throw error
  }
}

export async function submitFeedback(messageContent, feedbackType, sessionId, username) {
  try {
    const response = await fetch(`${API_BASE_URL}/feedback/submit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({
        session_id: sessionId,
        message_content: messageContent,
        feedback_type: feedbackType,
        username: username,
      }),
    })
    if (!response.ok) throw new Error('Failed to submit feedback')
    return await response.json()
  } catch (error) {
    console.error('Error submitting feedback:', error)
    throw error
  }
}

export async function getFeedbackStats() {
  try {
    const response = await fetch(`${API_BASE_URL}/feedback/stats`, {
      headers: { ...authHeaders() },
    })
    if (!response.ok) throw new Error('Failed to get feedback stats')
    return await response.json()
  } catch (error) {
    console.error('Error getting feedback stats:', error)
    throw error
  }
}

export async function getConversations(username) {
  try {
    const response = await fetch(`${API_BASE_URL}/chat/conversations/${username}`, {
      headers: { ...authHeaders() },
    })
    if (!response.ok) throw new Error('Failed to fetch conversations')
    const data = await response.json()
    return data.conversations || []
  } catch (error) {
    console.error('Error fetching conversations:', error)
    return []
  }
}

export async function getChatHistory(sessionId, limit = 100) {
  try {
    const response = await fetch(`${API_BASE_URL}/chat/history/session/${sessionId}?limit=${limit}`, {
      headers: { ...authHeaders() },
    })
    if (!response.ok) throw new Error('Failed to fetch chat history')
    const data = await response.json()
    return data.messages || []
  } catch (error) {
    console.error('Error fetching chat history:', error)
    return []
  }
}
