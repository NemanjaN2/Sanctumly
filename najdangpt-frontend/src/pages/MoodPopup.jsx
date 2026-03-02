import { useState, useEffect } from 'react'
import { getMoodToday, moodCheckin } from '../api/mood'

const MOODS = [
  { score: 1, emoji: '😞', label: 'Awful' },
  { score: 2, emoji: '😕', label: 'Bad' },
  { score: 3, emoji: '😐', label: 'Okay' },
  { score: 4, emoji: '🙂', label: 'Good' },
  { score: 5, emoji: '😊', label: 'Great' },
]

export default function MoodPopup({ user, onClose }) {
  const [show, setShow] = useState(false)
  const [selected, setSelected] = useState(null)
  const [note, setNote] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [done, setDone] = useState(false)

  useEffect(() => {
    checkTodayMood()
  }, [])

  async function checkTodayMood() {
    try {
      const data = await getMoodToday(user.username)
      if (!data.checked_in) {
        // Small delay so it doesn't flash immediately
        setTimeout(() => setShow(true), 1500)
      }
    } catch (err) {
      // Silently fail - don't block the user
      console.error('Mood check failed:', err)
    }
  }

  async function handleSubmit() {
    if (!selected) return
    try {
      setSubmitting(true)
      const sessionId = localStorage.getItem('session_id') || 'web'
      await moodCheckin(user.username, sessionId, selected, note || null)
      setDone(true)
      setTimeout(() => {
        setShow(false)
        onClose?.()
      }, 1200)
    } catch (err) {
      console.error('Mood checkin failed:', err)
    } finally {
      setSubmitting(false)
    }
  }

  function handleDismiss() {
    setShow(false)
    onClose?.()
  }

  if (!show) return null

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      zIndex: 9999,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'rgba(0,0,0,0.6)',
      backdropFilter: 'blur(4px)',
      animation: 'fadeIn 0.3s ease'
    }}>
      <div style={{
        background: 'var(--bg-secondary, #16213e)',
        borderRadius: '1.25rem',
        padding: '2rem',
        maxWidth: '360px',
        width: '90%',
        textAlign: 'center',
        border: '1px solid var(--border-subtle, rgba(255,255,255,0.1))',
        animation: 'slideUp 0.3s ease'
      }}>
        {done ? (
          <>
            <div style={{ fontSize: '3rem', marginBottom: '0.75rem' }}>✨</div>
            <div style={{ fontSize: '1.125rem', fontWeight: 600, color: 'var(--text-primary, #e0e0e0)' }}>
              Thanks for checking in!
            </div>
          </>
        ) : (
          <>
            <div style={{ fontSize: '1.125rem', fontWeight: 600, color: 'var(--text-primary, #e0e0e0)', marginBottom: '0.25rem' }}>
              How are you feeling today?
            </div>
            <div style={{ fontSize: '0.8125rem', color: 'var(--text-tertiary, #888)', marginBottom: '1.25rem' }}>
              Your daily wellness check-in
            </div>

            <div style={{ display: 'flex', justifyContent: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
              {MOODS.map(m => (
                <button
                  key={m.score}
                  onClick={() => setSelected(m.score)}
                  style={{
                    fontSize: '2rem',
                    padding: '0.5rem',
                    borderRadius: '1rem',
                    border: selected === m.score ? '2px solid #667eea' : '2px solid transparent',
                    background: selected === m.score ? 'rgba(102,126,234,0.15)' : 'transparent',
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                    transform: selected === m.score ? 'scale(1.2)' : 'scale(1)'
                  }}
                  title={m.label}
                >
                  {m.emoji}
                </button>
              ))}
            </div>

            {selected && (
              <div style={{ fontSize: '0.875rem', color: '#667eea', fontWeight: 500, marginBottom: '0.75rem' }}>
                {MOODS[selected - 1].label}
              </div>
            )}

            {selected && (
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="Add a note (optional)..."
                maxLength={500}
                rows={2}
                style={{
                  width: '100%',
                  background: 'var(--bg-primary, #0f0f23)',
                  border: '1px solid var(--border-subtle, rgba(255,255,255,0.1))',
                  borderRadius: '0.75rem',
                  padding: '0.625rem',
                  color: 'var(--text-primary, #e0e0e0)',
                  fontSize: '0.8125rem',
                  resize: 'none',
                  marginBottom: '1rem',
                  outline: 'none',
                  fontFamily: 'inherit',
                  boxSizing: 'border-box'
                }}
              />
            )}

            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button
                onClick={handleDismiss}
                style={{
                  flex: 1,
                  padding: '0.625rem',
                  background: 'transparent',
                  border: '1px solid var(--border-subtle, rgba(255,255,255,0.15))',
                  borderRadius: '0.75rem',
                  color: 'var(--text-secondary, #aaa)',
                  fontSize: '0.875rem',
                  cursor: 'pointer'
                }}
              >
                Skip
              </button>
              <button
                onClick={handleSubmit}
                disabled={!selected || submitting}
                style={{
                  flex: 1,
                  padding: '0.625rem',
                  background: selected ? 'linear-gradient(135deg, #667eea, #764ba2)' : 'rgba(255,255,255,0.1)',
                  border: 'none',
                  borderRadius: '0.75rem',
                  color: '#fff',
                  fontSize: '0.875rem',
                  fontWeight: 600,
                  cursor: selected ? 'pointer' : 'default',
                  opacity: !selected || submitting ? 0.5 : 1
                }}
              >
                {submitting ? 'Saving...' : 'Save'}
              </button>
            </div>
          </>
        )}
      </div>

      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes slideUp {
          from { opacity: 0; transform: translateY(20px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  )
}
