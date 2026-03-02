import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { getMoodHistory, moodCheckin } from '../api/mood'

const MOODS = [
  { score: 1, emoji: '😞', label: 'Awful', color: '#ef4444' },
  { score: 2, emoji: '😕', label: 'Bad', color: '#f97316' },
  { score: 3, emoji: '😐', label: 'Okay', color: '#eab308' },
  { score: 4, emoji: '🙂', label: 'Good', color: '#22c55e' },
  { score: 5, emoji: '😊', label: 'Great', color: '#667eea' },
]

export default function WellnessPage({ user }) {
  const navigate = useNavigate()
  const [history, setHistory] = useState(null)
  const [loading, setLoading] = useState(true)
  const [days, setDays] = useState(30)
  const [checkinScore, setCheckinScore] = useState(null)
  const [checkinNote, setCheckinNote] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    loadHistory()
  }, [days])

  async function loadHistory() {
    try {
      setLoading(true)
      const data = await getMoodHistory(user.username, days)
      setHistory(data)
    } catch (err) {
      console.error('Failed to load mood history:', err)
    } finally {
      setLoading(false)
    }
  }

  async function handleCheckin() {
    if (!checkinScore) return
    try {
      setSubmitting(true)
      const sessionId = localStorage.getItem('session_id') || 'web'
      await moodCheckin(user.username, sessionId, checkinScore, checkinNote || null)
      setCheckinScore(null)
      setCheckinNote('')
      loadHistory()
    } catch (err) {
      console.error('Checkin failed:', err)
    } finally {
      setSubmitting(false)
    }
  }

  // Build chart data - last N days with gaps for missing days
  function getChartData() {
    if (!history || !history.entries.length) return []
    const map = {}
    history.entries.forEach(e => { map[e.date] = e })
    const result = []
    const now = new Date()
    for (let i = days - 1; i >= 0; i--) {
      const d = new Date(now)
      d.setDate(d.getDate() - i)
      const key = d.toISOString().split('T')[0]
      result.push({
        date: key,
        shortDate: `${d.getDate()}/${d.getMonth() + 1}`,
        entry: map[key] || null
      })
    }
    return result
  }

  const chartData = getChartData()
  const maxBarHeight = 160

  return (
    <div style={{
      minHeight: '100vh',
      background: 'var(--bg-primary, #0f0f23)',
      color: 'var(--text-primary, #e0e0e0)'
    }}>
      {/* Header */}
      <div style={{
        padding: '1rem 1.5rem',
        borderBottom: '1px solid var(--border-subtle, rgba(255,255,255,0.08))',
        display: 'flex',
        alignItems: 'center',
        gap: '1rem',
        background: 'var(--bg-secondary, #16213e)'
      }}>
        <button
          onClick={() => navigate('/chat')}
          style={{
            background: 'none',
            border: 'none',
            color: 'var(--accent, #667eea)',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            fontSize: '0.9375rem',
            padding: '0.375rem 0.75rem',
            borderRadius: '0.5rem',
            transition: 'background 0.2s'
          }}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="15 18 9 12 15 6" />
          </svg>
          Back to Chat
        </button>
        <h1 style={{
          fontSize: '1.125rem',
          fontWeight: 600,
          background: 'linear-gradient(135deg, #667eea, #764ba2)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent'
        }}>
          My Wellness
        </h1>
      </div>

      <div style={{ maxWidth: '700px', margin: '0 auto', padding: '1.5rem' }}>

        {/* Quick Check-in Card */}
        <div style={{
          background: 'var(--bg-secondary, #16213e)',
          borderRadius: '1rem',
          padding: '1.5rem',
          marginBottom: '1.5rem',
          border: '1px solid var(--border-subtle, rgba(255,255,255,0.08))'
        }}>
          <h2 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '1rem', color: 'var(--text-primary, #e0e0e0)' }}>
            How are you feeling right now?
          </h2>
          <div style={{ display: 'flex', justifyContent: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
            {MOODS.map(m => (
              <button
                key={m.score}
                onClick={() => setCheckinScore(m.score)}
                style={{
                  fontSize: '2rem',
                  padding: '0.5rem',
                  borderRadius: '1rem',
                  border: checkinScore === m.score ? `2px solid ${m.color}` : '2px solid transparent',
                  background: checkinScore === m.score ? `${m.color}22` : 'transparent',
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                  transform: checkinScore === m.score ? 'scale(1.15)' : 'scale(1)'
                }}
                title={m.label}
              >
                {m.emoji}
              </button>
            ))}
          </div>
          {checkinScore && (
            <div style={{ fontSize: '0.875rem', textAlign: 'center', color: MOODS[checkinScore - 1].color, marginBottom: '0.75rem', fontWeight: 500 }}>
              {MOODS[checkinScore - 1].label}
            </div>
          )}
          {checkinScore && (
            <>
              <textarea
                value={checkinNote}
                onChange={(e) => setCheckinNote(e.target.value)}
                placeholder="Add a note (optional)..."
                maxLength={500}
                rows={2}
                style={{
                  width: '100%',
                  background: 'var(--bg-primary, #0f0f23)',
                  border: '1px solid var(--border-subtle, rgba(255,255,255,0.1))',
                  borderRadius: '0.75rem',
                  padding: '0.75rem',
                  color: 'var(--text-primary, #e0e0e0)',
                  fontSize: '0.875rem',
                  resize: 'none',
                  marginBottom: '0.75rem',
                  outline: 'none',
                  fontFamily: 'inherit'
                }}
              />
              <button
                onClick={handleCheckin}
                disabled={submitting}
                style={{
                  width: '100%',
                  padding: '0.625rem',
                  background: 'linear-gradient(135deg, #667eea, #764ba2)',
                  border: 'none',
                  borderRadius: '0.75rem',
                  color: '#fff',
                  fontSize: '0.9375rem',
                  fontWeight: 600,
                  cursor: submitting ? 'not-allowed' : 'pointer',
                  opacity: submitting ? 0.7 : 1
                }}
              >
                {submitting ? 'Saving...' : 'Save Check-in'}
              </button>
            </>
          )}
        </div>

        {/* Stats Card */}
        {history && history.entries.length > 0 && (
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, 1fr)',
            gap: '0.75rem',
            marginBottom: '1.5rem'
          }}>
            {[
              { label: 'Average Mood', value: history.average ? MOODS[Math.round(history.average) - 1]?.emoji + ' ' + history.average : '-' },
              { label: 'Check-ins', value: history.count },
              { label: 'Current Streak', value: getStreak(history.entries) + ' days' },
            ].map((stat, i) => (
              <div key={i} style={{
                background: 'var(--bg-secondary, #16213e)',
                borderRadius: '0.75rem',
                padding: '1rem',
                textAlign: 'center',
                border: '1px solid var(--border-subtle, rgba(255,255,255,0.08))'
              }}>
                <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#667eea' }}>{stat.value}</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary, #888)', marginTop: '0.25rem' }}>{stat.label}</div>
              </div>
            ))}
          </div>
        )}

        {/* Time Range Selector */}
        <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
          {[7, 30, 90].map(d => (
            <button
              key={d}
              onClick={() => setDays(d)}
              style={{
                padding: '0.375rem 0.875rem',
                borderRadius: '0.5rem',
                border: 'none',
                background: days === d ? '#667eea' : 'var(--bg-secondary, #16213e)',
                color: days === d ? '#fff' : 'var(--text-secondary, #aaa)',
                fontSize: '0.8125rem',
                fontWeight: 500,
                cursor: 'pointer'
              }}
            >
              {d}d
            </button>
          ))}
        </div>

        {/* Mood Chart */}
        <div style={{
          background: 'var(--bg-secondary, #16213e)',
          borderRadius: '1rem',
          padding: '1.5rem',
          border: '1px solid var(--border-subtle, rgba(255,255,255,0.08))'
        }}>
          <h2 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '1rem' }}>Mood History</h2>
          
          {loading ? (
            <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-tertiary, #888)' }}>Loading...</div>
          ) : chartData.length === 0 || !history?.entries?.length ? (
            <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-tertiary, #888)' }}>
              No mood data yet. Start by checking in above!
            </div>
          ) : (
            <>
              {/* Y-axis labels + bars */}
              <div style={{ display: 'flex', gap: '0.25rem' }}>
                {/* Y axis */}
                <div style={{
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  height: maxBarHeight + 'px',
                  paddingRight: '0.5rem',
                  fontSize: '0.75rem'
                }}>
                  {[...MOODS].reverse().map(m => (
                    <div key={m.score} style={{ lineHeight: '1' }}>{m.emoji}</div>
                  ))}
                </div>

                {/* Bars */}
                <div style={{
                  flex: 1,
                  display: 'flex',
                  alignItems: 'flex-end',
                  gap: days <= 7 ? '4px' : days <= 30 ? '2px' : '1px',
                  height: maxBarHeight + 'px',
                  borderBottom: '1px solid rgba(255,255,255,0.1)'
                }}>
                  {chartData.map((d, i) => {
                    const barH = d.entry ? (d.entry.mood_score / 5) * maxBarHeight : 0
                    const mood = d.entry ? MOODS[d.entry.mood_score - 1] : null
                    return (
                      <div
                        key={i}
                        style={{
                          flex: 1,
                          display: 'flex',
                          flexDirection: 'column',
                          alignItems: 'center',
                          justifyContent: 'flex-end',
                          height: '100%',
                          position: 'relative'
                        }}
                        title={d.entry ? `${d.date}: ${d.entry.emoji} ${MOODS[d.entry.mood_score - 1].label}${d.entry.note ? ' - ' + d.entry.note : ''}` : `${d.date}: No check-in`}
                      >
                        {d.entry ? (
                          <div style={{
                            width: '100%',
                            maxWidth: days <= 7 ? '32px' : days <= 30 ? '16px' : '8px',
                            height: barH + 'px',
                            background: `linear-gradient(180deg, ${mood.color}, ${mood.color}88)`,
                            borderRadius: '3px 3px 0 0',
                            transition: 'height 0.3s ease'
                          }} />
                        ) : (
                          <div style={{
                            width: '100%',
                            maxWidth: days <= 7 ? '32px' : days <= 30 ? '16px' : '8px',
                            height: '2px',
                            background: 'rgba(255,255,255,0.05)',
                            borderRadius: '1px'
                          }} />
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* X axis labels */}
              {days <= 30 && (
                <div style={{
                  display: 'flex',
                  marginLeft: '2rem',
                  marginTop: '0.375rem'
                }}>
                  {chartData.map((d, i) => {
                    const showLabel = days <= 7 || i % Math.ceil(days / 10) === 0
                    return (
                      <div key={i} style={{
                        flex: 1,
                        fontSize: '0.625rem',
                        color: 'var(--text-tertiary, #666)',
                        textAlign: 'center'
                      }}>
                        {showLabel ? d.shortDate : ''}
                      </div>
                    )
                  })}
                </div>
              )}
            </>
          )}
        </div>

        {/* Recent Entries */}
        {history && history.entries.length > 0 && (
          <div style={{
            marginTop: '1.5rem',
            background: 'var(--bg-secondary, #16213e)',
            borderRadius: '1rem',
            padding: '1.5rem',
            border: '1px solid var(--border-subtle, rgba(255,255,255,0.08))'
          }}>
            <h2 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '1rem' }}>Recent Check-ins</h2>
            {[...history.entries].reverse().slice(0, 10).map((e, i) => (
              <div key={i} style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.75rem',
                padding: '0.625rem 0',
                borderBottom: i < Math.min(history.entries.length, 10) - 1 ? '1px solid rgba(255,255,255,0.05)' : 'none'
              }}>
                <span style={{ fontSize: '1.5rem' }}>{e.emoji}</span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: '0.875rem', fontWeight: 500 }}>{e.date}</div>
                  {e.note && <div style={{ fontSize: '0.8125rem', color: 'var(--text-tertiary, #888)', marginTop: '0.125rem' }}>{e.note}</div>}
                </div>
                <div style={{
                  fontSize: '0.75rem',
                  padding: '0.25rem 0.5rem',
                  borderRadius: '0.375rem',
                  background: `${MOODS[e.mood_score - 1]?.color}22`,
                  color: MOODS[e.mood_score - 1]?.color,
                  fontWeight: 500
                }}>
                  {MOODS[e.mood_score - 1]?.label}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function getStreak(entries) {
  if (!entries.length) return 0
  const dates = new Set(entries.map(e => e.date))
  let streak = 0
  const now = new Date()
  for (let i = 0; i < 365; i++) {
    const d = new Date(now)
    d.setDate(d.getDate() - i)
    const key = d.toISOString().split('T')[0]
    if (dates.has(key)) {
      streak++
    } else {
      break
    }
  }
  return streak
}
