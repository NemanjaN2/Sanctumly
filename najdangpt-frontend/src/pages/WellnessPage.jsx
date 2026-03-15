import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { getMoodHistory, moodCheckin } from '../api/mood'

const MOODS = [
  { score: 1, emoji: '😞', label: 'Awful', color: '#ff453a' },
  { score: 2, emoji: '😕', label: 'Bad', color: '#ff9f0a' },
  { score: 3, emoji: '😐', label: 'Okay', color: '#ffd60a' },
  { score: 4, emoji: '🙂', label: 'Good', color: '#30d158' },
  { score: 5, emoji: '😊', label: 'Great', color: '#8b8bf5' },
]

export default function WellnessPage({ user }) {
  const navigate = useNavigate()
  const [history, setHistory] = useState(null)
  const [loading, setLoading] = useState(true)
  const [days, setDays] = useState(30)
  const [checkinScore, setCheckinScore] = useState(null)
  const [checkinNote, setCheckinNote] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => { loadHistory() }, [days])

  async function loadHistory() {
    if (!user?.username) return
    try { setLoading(true); setHistory(await getMoodHistory(user.username, days)) }
    catch {} finally { setLoading(false) }
  }

  async function handleCheckin() {
    if (!checkinScore) return
    try {
      setSubmitting(true)
      await moodCheckin(user.username, localStorage.getItem('session_id') || 'web', checkinScore, checkinNote || null)
      setCheckinScore(null); setCheckinNote(''); loadHistory()
    } catch {} finally { setSubmitting(false) }
  }

  function getChartData() {
    if (!history?.entries?.length) return []
    const map = {}; history.entries.forEach(e => { map[e.date] = e })
    const result = []; const now = new Date()
    for (let i = days - 1; i >= 0; i--) {
      const d = new Date(now); d.setDate(d.getDate() - i)
      const key = d.toISOString().split('T')[0]
      result.push({ date: key, short: `${d.getDate()}/${d.getMonth()+1}`, entry: map[key] || null })
    }
    return result
  }

  function getStreak() {
    if (!history?.entries?.length) return 0
    const dates = new Set(history.entries.map(e => e.date))
    let streak = 0; const now = new Date()
    for (let i = 0; i < 365; i++) {
      const d = new Date(now); d.setDate(d.getDate() - i)
      if (dates.has(d.toISOString().split('T')[0])) streak++; else break
    }
    return streak
  }

  const chartData = getChartData()
  const selectedMood = checkinScore ? MOODS[checkinScore - 1] : null

  return (
    <div className="wellness-page">
      <header className="wellness-header">
        <button className="admin-back" onClick={() => navigate('/chat')}>← Back to Chat</button>
        <span className="admin-title">My Wellness</span>
      </header>

      <div className="wellness-content">
        {/* Check-in */}
        <div className="w-card">
          <h2 className="w-card-title">How are you feeling right now?</h2>
          <div className="w-moods">
            {MOODS.map(m => (
              <button key={m.score} className={`w-mood-btn ${checkinScore === m.score ? 'active' : ''}`}
                style={{ '--mood-color': m.color }} onClick={() => setCheckinScore(m.score)}>
                <span className="w-mood-emoji">{m.emoji}</span>
              </button>
            ))}
          </div>
          {selectedMood && (
            <div className="w-mood-label" style={{ color: selectedMood.color }}>{selectedMood.label}</div>
          )}
          {checkinScore && (
            <>
              <textarea className="w-note" value={checkinNote} onChange={e => setCheckinNote(e.target.value)}
                placeholder="Add a note (optional)…" rows={2} maxLength={500} />
              <button className="w-checkin-btn" onClick={handleCheckin} disabled={submitting}>
                {submitting ? 'Saving…' : 'Save Check-in'}
              </button>
            </>
          )}
        </div>

        {/* Stats */}
        {history && history.count > 0 && (
          <div className="w-stats">
            <div className="w-stat">
              <div className="w-stat-val">
                {history.average ? `${MOODS[Math.round(history.average)-1]?.emoji} ${history.average.toFixed(1)}` : '-'}
              </div>
              <div className="w-stat-label">Average</div>
            </div>
            <div className="w-stat">
              <div className="w-stat-val">{history.count}</div>
              <div className="w-stat-label">Check-ins</div>
            </div>
            <div className="w-stat">
              <div className="w-stat-val">{getStreak()}d</div>
              <div className="w-stat-label">Streak</div>
            </div>
          </div>
        )}

        {/* Time range */}
        <div className="w-range">
          {[7, 30, 90].map(d => (
            <button key={d} className={`w-range-btn ${days === d ? 'active' : ''}`} onClick={() => setDays(d)}>{d}d</button>
          ))}
        </div>

        {/* Chart */}
        <div className="w-card">
          <h2 className="w-card-title">Mood History</h2>
          {loading ? (
            <div className="w-empty">Loading…</div>
          ) : !chartData.length || !history?.entries?.length ? (
            <div className="w-empty">No mood data yet. Start by checking in above!</div>
          ) : (
            <div className="w-chart">
              <div className="w-chart-y">
                {[...MOODS].reverse().map(m => <div key={m.score} className="w-chart-y-item">{m.emoji}</div>)}
              </div>
              <div className="w-chart-bars">
                {chartData.map((d, i) => (
                  <div key={i} className="w-bar-col" title={d.entry ? `${d.date}: ${MOODS[d.entry.mood_score-1]?.label}` : `${d.date}: No data`}>
                    {d.entry ? (
                      <div className="w-bar" style={{
                        height: `${(d.entry.mood_score / 5) * 100}%`,
                        background: MOODS[d.entry.mood_score - 1]?.color
                      }} />
                    ) : (
                      <div className="w-bar-empty" />
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Recent entries */}
        {history && history.count > 0 && (
          <div className="w-card">
            <h2 className="w-card-title">Recent Check-ins</h2>
            <div className="w-entries">
              {[...history.entries].reverse().slice(0, 10).map((e, i) => {
                const mood = MOODS[e.mood_score - 1]
                return (
                  <div key={i} className="w-entry">
                    <span className="w-entry-emoji">{e.emoji}</span>
                    <div className="w-entry-info">
                      <span className="w-entry-date">{e.date}</span>
                      {e.note && <span className="w-entry-note">{e.note}</span>}
                    </div>
                    {mood && <span className="w-entry-tag" style={{ background: `${mood.color}18`, color: mood.color }}>{mood.label}</span>}
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
