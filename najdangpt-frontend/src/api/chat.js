const API_BASE_URL = import.meta.env.VITE_API_URL || 'https://sanctumly-production.up.railway.app'

export async function sendMessage(message, sessionId, username, personality = 'default', image = null) {
  try {
    const body = {
      message,
      session_id: sessionId,
      username,
      personality
    }
    if (image) {
      body.image = image
    }
    const response = await fetch(`${API_BASE_URL}/chat/message`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    })
    if (!response.ok) {
      throw new Error('Failed to send message')
    }
    const data = await response.json()
    return data
  } catch (error) {
    console.error('Error sending message:', error)
    throw error
  }
}

export async function clearChat(sessionId) {
  try {
    const response = await fetch(`${API_BASE_URL}/chat/clear/${sessionId}`, {
      method: 'DELETE',
    })
    if (!response.ok) {
      throw new Error('Failed to clear chat')
    }
    const data = await response.json()
    return data
  } catch (error) {
    console.error('Error clearing chat:', error)
    throw error
  }
}

export async function submitFeedback(messageContent, feedbackType, sessionId, username) {
  try {
    const response = await fetch(`${API_BASE_URL}/feedback/submit`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        session_id: sessionId,
        message_content: messageContent,
        feedback_type: feedbackType,
        username: username
      }),
    })
    if (!response.ok) {
      throw new Error('Failed to submit feedback')
    }
    const data = await response.json()
    return data
  } catch (error) {
    console.error('Error submitting feedback:', error)
    throw error
  }
}

export async function getFeedbackStats() {
  try {
    const response = await fetch(`${API_BASE_URL}/feedback/stats`)
    
    if (!response.ok) {
      throw new Error('Failed to get feedback stats')
    }
    const data = await response.json()
    return data
  } catch (error) {
    console.error('Error getting feedback stats:', error)
    throw error
  }
}

// ===== Chat History Functions =====

export async function getConversations(username) {
  try {
    const response = await fetch(`${API_BASE_URL}/chat/conversations/${username}`)
    if (!response.ok) {
      throw new Error('Failed to fetch conversations')
    }
    const data = await response.json()
    return data.conversations || []
  } catch (error) {
    console.error('Error fetching conversations:', error)
    return []
  }
}

export async function getChatHistory(sessionId, limit = 100) {
  try {
    const response = await fetch(`${API_BASE_URL}/chat/history/session/${sessionId}?limit=${limit}`)
    if (!response.ok) {
      throw new Error('Failed to fetch chat history')
    }
    const data = await response.json()
    return data.messages || []
  } catch (error) {
    console.error('Error fetching chat history:', error)
    return []
  }
}      }),
    })

    if (!response.ok) {
      throw new Error('Failed to submit feedback')
    }

    const data = await response.json()
    return data
  } catch (error) {
    console.error('Error submitting feedback:', error)
    throw error
  }
}

export async function getFeedbackStats() {
  try {
    const response = await fetch(`${API_BASE_URL}/feedback/stats`)
    
    if (!response.ok) {
      throw new Error('Failed to get feedback stats')
    }

    const data = await response.json()
    return data
  } catch (error) {
    console.error('Error getting feedback stats:', error)
    throw error
  }
}
