import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { login, signup } from '../api/auth'

export default function LoginPage({ onLogin }) {
  const [isLogin, setIsLogin] = useState(true)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [email, setEmail] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const response = isLogin ? await login(username, password) : await signup(username, password, email)
      if (response.success) {
        if (response.session_id) {
          localStorage.setItem('session_id', response.session_id)
        }
        localStorage.setItem('username', response.user.username)
        onLogin(response.user)
        navigate('/chat')
      }
    } catch (err) {
      setError(err.message || 'Authentication failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <img src="/logo.png" alt="" className="login-logo" />
        <h1 className="login-title">Sanctumly</h1>
        <p className="login-sub">Your AI Wellness Companion</p>

        <div className="login-toggle">
          <button className={`login-tab ${isLogin ? 'active' : ''}`} onClick={() => setIsLogin(true)}>Login</button>
          <button className={`login-tab ${!isLogin ? 'active' : ''}`} onClick={() => setIsLogin(false)}>Sign Up</button>
        </div>

        {error && <div className="notif error">{error}</div>}

        <form onSubmit={handleSubmit} className="login-form">
          <div className="login-field">
            <label>Username</label>
            <input type="text" value={username} onChange={e => setUsername(e.target.value)}
              placeholder="Enter your username" required autoComplete="username" className="ib-text" />
          </div>

          {!isLogin && (
            <div className="login-field">
              <label>Email (optional)</label>
              <input type="email" value={email} onChange={e => setEmail(e.target.value)}
                placeholder="your@email.com" autoComplete="email" className="ib-text" />
            </div>
          )}

          <div className="login-field">
            <label>Password</label>
            <input type="password" value={password} onChange={e => setPassword(e.target.value)}
              placeholder="Enter your password" required autoComplete={isLogin ? 'current-password' : 'new-password'} className="ib-text" />
          </div>

          <button type="submit" disabled={loading} className="login-submit">
            {loading ? 'Please wait…' : isLogin ? 'Login' : 'Create Account'}
          </button>
        </form>
      </div>
    </div>
  )
}
