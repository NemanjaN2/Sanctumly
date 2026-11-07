const API_URL = import.meta.env.VITE_API_URL || 'https://sanctumly-production.up.railway.app'

export async function login(username, password) {
  const response = await fetch(`${API_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Login failed')
  }
  const data = await response.json()
  if (data.session_id) localStorage.setItem('sanctumly_auth_token', data.session_id)
  return data
}

export async function signup(username, password, email) {
  const response = await fetch(`${API_URL}/auth/signup`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password, email }),
  })
  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Signup failed')
  }
  const data = await response.json()
  if (data.session_id) localStorage.setItem('sanctumly_auth_token', data.session_id)
  return data
}

export async function logout() {
  const token = localStorage.getItem('sanctumly_auth_token')
  try {
    if (token) {
      await fetch(`${API_URL}/auth/logout`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
    }
  } finally {
    localStorage.removeItem('sanctumly_auth_token')
    localStorage.removeItem('session_id')
    localStorage.removeItem('username')
  }
}
