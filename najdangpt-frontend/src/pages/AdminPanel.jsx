import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { getSettings, saveSetting } from '../api/admin'
import TherapistKnowledgeBase from './TherapistKnowledgeBase'

export default function AdminPanel({ user, onLogout }) {
  const [systemPrompt, setSystemPrompt] = useState('')
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState(false)

  useEffect(() => { loadSettings() }, [])

  const loadSettings = async () => {
    try { const s = await getSettings(); setSystemPrompt(s.system_prompt || '') } catch {}
  }

  const handleSave = async () => {
    setLoading(true); setSuccess(false)
    try { await saveSetting('system_prompt', systemPrompt); setSuccess(true); setTimeout(() => setSuccess(false), 3000) }
    catch { alert('Failed to save') }
    finally { setLoading(false) }
  }

  if (!user?.is_admin) {
    return (
      <div className="admin-denied">
        <div className="admin-denied-card">
          <h1>Access Denied</h1>
          <p>You need admin privileges to access this page.</p>
          <Link to="/chat" className="ib-send" style={{ display: 'inline-flex', padding: '8px 20px', borderRadius: '8px', textDecoration: 'none', fontSize: '14px' }}>Go to Chat</Link>
        </div>
      </div>
    )
  }

  return (
    <div className="admin-page">
      <header className="admin-header">
        <div className="admin-header-inner">
          <div className="admin-header-left">
            <Link to="/chat" className="admin-back">← Back to Chat</Link>
            <span className="admin-title">Admin Panel</span>
          </div>
          <button className="sb-link danger" onClick={onLogout} style={{ margin: 0, padding: '6px 14px', borderRadius: '6px' }}>Logout</button>
        </div>
      </header>

      <div className="admin-content">
        {/* System Config */}
        <div className="admin-card">
          <h2 className="admin-card-title">System Configuration</h2>
          {success && <div className="notif ok">Settings saved</div>}
          <div className="login-field">
            <label>System Prompt</label>
            <textarea value={systemPrompt} onChange={e => setSystemPrompt(e.target.value)}
              className="admin-textarea" rows="12" placeholder="Enter custom system prompt…" />
            <span className="admin-hint">Added to the AI's instructions. Customize behavior, language detection, etc.</span>
          </div>
          <button onClick={handleSave} disabled={loading} className="admin-save">{loading ? 'Saving…' : 'Save Settings'}</button>
        </div>

        {/* Therapist KB */}
        <TherapistKnowledgeBase />

        {/* Info cards */}
        <div className="admin-info-grid">
          <div className="admin-info-card">
            <div className="admin-info-label">Admin User</div>
            <div className="admin-info-value">{user.username}</div>
          </div>
          <div className="admin-info-card">
            <div className="admin-info-label">Role</div>
            <div className="admin-info-value">{user.is_creator ? <span className="sb-creator-tag">Creator</span> : 'Admin'}</div>
          </div>
          <div className="admin-info-card">
            <div className="admin-info-label">Status</div>
            <div className="admin-info-value" style={{ color: 'var(--green)' }}>● Active</div>
          </div>
        </div>
      </div>
    </div>
  )
}
