import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { getSettings, saveSetting } from '../api/admin'
import TherapistKnowledgeBase from './TherapistKnowledgeBase'

export default function AdminPanel({ user, onLogout }) {
  const [systemPrompt, setSystemPrompt] = useState('')
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    loadSettings()
  }, [])

  const loadSettings = async () => {
    try {
      const settings = await getSettings()
      setSystemPrompt(settings.system_prompt || '')
    } catch (err) {
      console.error('Failed to load settings:', err)
    }
  }

  const handleSave = async () => {
    setLoading(true)
    setSuccess(false)

    try {
      await saveSetting('system_prompt', systemPrompt)
      setSuccess(true)
      setTimeout(() => setSuccess(false), 3000)
    } catch (err) {
      console.error('Failed to save:', err)
      alert('Failed to save settings')
    } finally {
      setLoading(false)
    }
  }

  if (!user?.is_admin) {
    return (
      <div style={{ 
        minHeight: '100vh', 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center',
        padding: '2rem'
      }}>
        <div className="glass-heavy" style={{ 
          padding: '2rem', 
          borderRadius: '1rem', 
          textAlign: 'center',
          maxWidth: '400px'
        }}>
          <h1 style={{ 
            fontSize: '1.5rem', 
            fontWeight: 600, 
            marginBottom: '1rem',
            color: 'var(--text-primary)'
          }}>
            Access Denied
          </h1>
          <p style={{ 
            color: 'var(--text-secondary)', 
            marginBottom: '1.5rem',
            fontSize: '0.9375rem'
          }}>
            You need admin privileges to access this page.
          </p>
          <Link to="/chat" className="btn btn-primary">
            Go to Chat
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-primary)' }}>
      {/* Header - Centered */}
      <div className="glass-heavy" style={{ 
        borderBottom: '1px solid var(--border-subtle)'
      }}>
        <div style={{
          maxWidth: '900px',
          margin: '0 auto',
          padding: '1rem 1.5rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '1rem'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <Link to="/chat" className="btn btn-secondary" style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '0.5rem',
              padding: '0.5rem 0.875rem'
            }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="19" y1="12" x2="5" y2="12"></line>
                <polyline points="12 19 5 12 12 5"></polyline>
              </svg>
              Back to Chat
            </Link>
            <h1 style={{ 
              fontSize: '1.25rem', 
              fontWeight: 600 
            }} className="gradient-text">
              Admin Panel
            </h1>
          </div>
          <button onClick={onLogout} className="btn btn-secondary" style={{
            padding: '0.5rem 0.875rem'
          }}>
            Logout
          </button>
        </div>
      </div>

      {/* Content - Centered with max-width */}
      <div style={{ 
        maxWidth: '900px', 
        margin: '0 auto',
        padding: '2rem 1.5rem'
      }}>
        {/* Main Configuration Card */}
        <div className="glass-heavy" style={{ 
          padding: '1.5rem',
          borderRadius: '0.75rem',
          marginBottom: '1.5rem'
        }}>
          <h2 style={{ 
            fontSize: '1.125rem', 
            fontWeight: 600,
            marginBottom: '1rem',
            color: 'var(--text-primary)'
          }}>
            System Configuration
          </h2>

          {success && (
            <div className="success-message" style={{ marginBottom: '1rem' }}>
              Settings saved successfully
            </div>
          )}

          <div style={{ marginBottom: '1.5rem' }}>
            <label style={{ 
              display: 'block', 
              fontSize: '0.875rem',
              fontWeight: 500,
              color: 'var(--text-secondary)',
              marginBottom: '0.5rem'
            }}>
              System Prompt
            </label>
            <textarea
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              className="input"
              rows="15"
              placeholder="Enter custom system prompt here..."
              style={{
                resize: 'vertical',
                fontFamily: 'inherit',
                fontSize: '0.875rem'
              }}
            />
            <p style={{ 
              fontSize: '0.8125rem',
              color: 'var(--text-tertiary)',
              marginTop: '0.5rem',
              lineHeight: 1.5
            }}>
              This will be added to the AI's instructions. Use this to customize behavior, add language detection, or any other custom instructions.
            </p>
          </div>

          <button
            onClick={handleSave}
            disabled={loading}
            className="btn btn-primary"
            style={{ minWidth: '120px' }}
          >
            {loading ? 'Saving...' : 'Save Settings'}
          </button>
        </div>

        {/* Therapist Knowledge Base */}
        <TherapistKnowledgeBase />

        {/* Info Cards */}
        <div style={{ 
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '1rem'
        }}>
          <div className="glass-heavy" style={{ 
            padding: '1rem',
            borderRadius: '0.75rem'
          }}>
            <div style={{ 
              fontSize: '0.8125rem',
              color: 'var(--text-tertiary)',
              marginBottom: '0.5rem',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              fontWeight: 600
            }}>
              Admin User
            </div>
            <div style={{ 
              fontSize: '1rem',
              fontWeight: 500,
              color: 'var(--text-primary)'
            }}>
              {user.username}
            </div>
          </div>

          <div className="glass-heavy" style={{ 
            padding: '1rem',
            borderRadius: '0.75rem'
          }}>
            <div style={{ 
              fontSize: '0.8125rem',
              color: 'var(--text-tertiary)',
              marginBottom: '0.5rem',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              fontWeight: 600
            }}>
              Role
            </div>
            <div style={{ 
              fontSize: '1rem',
              fontWeight: 500,
              color: 'var(--text-primary)',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem'
            }}>
              {user.is_creator ? (
                <>
                  <span className="user-badge">Creator</span>
                </>
              ) : (
                'Admin'
              )}
            </div>
          </div>

          <div className="glass-heavy" style={{ 
            padding: '1rem',
            borderRadius: '0.75rem'
          }}>
            <div style={{ 
              fontSize: '0.8125rem',
              color: 'var(--text-tertiary)',
              marginBottom: '0.5rem',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              fontWeight: 600
            }}>
              Status
            </div>
            <div style={{ 
              fontSize: '1rem',
              fontWeight: 500,
              color: 'var(--success)',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem'
            }}>
              <span style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                background: 'var(--success)',
                display: 'inline-block'
              }}></span>
              Active
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
