import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { getAIControlOverview, updateAIProviderOverride } from '../api/aiControl'
import './AIControlCenter.css'

const number = (value, digits = 0) => Number(value ?? 0).toLocaleString(undefined, {
  minimumFractionDigits: 0,
  maximumFractionDigits: digits,
})

const dateTime = (value) => value ? new Date(value).toLocaleString() : '—'
const dateTimeUtc = (value) => value ? `${new Date(value).toLocaleString(undefined, { timeZone: 'UTC', dateStyle: 'medium', timeStyle: 'short' })} UTC` : '—'
const time = (value) => value ? new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '—'

function StatusPill({ value }) {
  const normalized = String(value || 'unknown').toLowerCase()
  const label = normalized.replaceAll('_', ' ')
  const tone = ['available', 'configured'].includes(normalized)
    ? 'good'
    : ['exhausted', 'cooldown', 'degraded'].includes(normalized)
      ? 'warn'
      : ['not_configured', 'unavailable'].includes(normalized)
        ? 'bad'
        : 'neutral'
  return <span className={`ai-status ai-status--${tone}`}><i />{label}</span>
}

function MetricCard({ label, value, detail, accent = '' }) {
  return (
    <article className="aic-metric-card">
      <div className="aic-label">{label}</div>
      <div className={`aic-metric-value ${accent}`}>{value}</div>
      {detail && <div className="aic-muted aic-metric-detail">{detail}</div>}
    </article>
  )
}

function Breakdown({ title, items, empty = 'No routing events recorded in this period.' }) {
  const rows = Object.entries(items || {}).sort((a, b) => b[1] - a[1])
  const max = Math.max(1, ...rows.map(([, value]) => Number(value) || 0))
  return (
    <section className="aic-panel">
      <div className="aic-section-heading"><h2>{title}</h2><span>Selected period</span></div>
      {rows.length ? (
        <div className="aic-breakdown-list">
          {rows.map(([label, value]) => (
            <div className="aic-breakdown-row" key={label}>
              <div className="aic-breakdown-meta"><span>{label.replaceAll('_', ' ')}</span><strong>{number(value)}</strong></div>
              <div className="aic-bar-track"><div className="aic-bar-fill" style={{ width: `${Math.max(2, Number(value) / max * 100)}%` }} /></div>
            </div>
          ))}
        </div>
      ) : <p className="aic-empty">{empty}</p>}
    </section>
  )
}

export default function AIControlCenter({ user, onLogout }) {
  const [data, setData] = useState(null)
  const [days, setDays] = useState(7)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [savingOverride, setSavingOverride] = useState(false)
  const [overrideMode, setOverrideMode] = useState('auto')
  const overrideModeTouched = useRef(false)
  const [duration, setDuration] = useState(60)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const refresh = useCallback(async (quiet = false) => {
    if (quiet) setRefreshing(true)
    else setLoading(true)
    try {
      const overview = await getAIControlOverview(days)
      setData(overview)
      if (!overrideModeTouched.current) setOverrideMode(overview.override?.active ? 'groq' : 'auto')
      setError('')
    } catch (err) {
      setError(err.status === 401
        ? 'Your session has expired. Sign out and sign back in to reconnect.'
        : err.status === 403
          ? 'Creator access is required to view this dashboard.'
          : err.message || 'Could not load AI provider diagnostics.')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [days])

  useEffect(() => {
    refresh()
    const interval = window.setInterval(() => refresh(true), 30000)
    return () => window.clearInterval(interval)
  }, [refresh])

  const quota = data?.providers?.cloudflare
  const used = Number(quota?.used_neurons || 0)
  const reserved = Number(quota?.reserved_neurons || 0)
  const budget = Number(quota?.sanctumly_neuron_budget || 0)
  const remaining = Number(quota?.remaining_estimate || 0)
  const quotaPercent = useMemo(() => budget > 0 ? Math.min(100, ((used + reserved) / budget) * 100) : 0, [budget, used, reserved])
  const activeOverride = Boolean(data?.override?.active)

  const handleOverride = async () => {
    if (overrideMode === 'groq') {
      const confirmed = window.confirm(
        `Force GPT-OSS-120B for all Sanctumly text requests for ${duration} minutes? This is a global override and affects every account. It will expire automatically.`,
      )
      if (!confirmed) return
    }

    setSavingOverride(true)
    setNotice('')
    try {
      await updateAIProviderOverride(overrideMode, Number(duration))
      overrideModeTouched.current = false
      setNotice(overrideMode === 'groq'
        ? `GPT-OSS is now forced globally for ${duration} minutes. Automatic expiry is enabled.`
        : 'Automatic routing restored. Qwen is eligible as the primary model again.')
      await refresh(true)
    } catch (err) {
      setError(err.message || 'Could not update provider routing.')
    } finally {
      setSavingOverride(false)
    }
  }

  const metrics = data?.metrics || {}
  const cloudflare = data?.providers?.cloudflare || {}
  const groq = data?.providers?.groq || {}
  const serper = data?.providers?.serper || {}

  return (
    <div className="aic-page">
      <header className="aic-header">
        <div className="aic-header-inner">
          <div className="aic-heading-lockup">
            <Link to="/chat" className="aic-back">← Back to Sanctumly</Link>
            <div className="aic-title-row">
              <div className="aic-mark">S</div>
              <div>
                <div className="aic-eyebrow">Creator console</div>
                <h1>AI Control Center</h1>
                <p>Model routing, shared provider quota and operational telemetry.</p>
              </div>
            </div>
          </div>
          <div className="aic-header-actions">
            <div className="aic-identity"><span className="aic-live-dot" />{user?.username || 'Creator'} · Creator</div>
            <button className="aic-button aic-button--quiet" onClick={() => refresh(true)} disabled={refreshing}>
              <span className={refreshing ? 'aic-spin' : ''}>↻</span> {refreshing ? 'Refreshing' : 'Refresh'}
            </button>
            <button className="aic-button aic-button--quiet" onClick={onLogout}>Log out</button>
          </div>
        </div>
      </header>

      <main className="aic-main">
        <div className="aic-toolbar">
          <div>
            <div className="aic-kicker">System overview</div>
            <p className="aic-muted">Global provider state applies to every Sanctumly account. Analytics exclude prompts and message content.</p>
          </div>
          <label className="aic-period-control">
            <span>Analytics period</span>
            <select value={days} onChange={event => setDays(Number(event.target.value))}>
              <option value={1}>Last 24 hours</option>
              <option value={7}>Last 7 days</option>
              <option value={30}>Last 30 days</option>
            </select>
          </label>
        </div>

        {error && <div className="aic-alert aic-alert--error" role="alert">{error}</div>}
        {notice && <div className="aic-alert aic-alert--success" role="status">{notice}</div>}

        {loading && !data ? (
          <div className="aic-loading"><span className="aic-spinner" />Loading provider telemetry…</div>
        ) : data ? (
          <>
            <section className="aic-metrics-grid">
              <MetricCard label="Requests · selected period" value={number(metrics.requests)} detail={`${number(metrics.successful_requests)} successful · ${number(metrics.failed_requests)} failed`} />
              <MetricCard label="Success rate" value={metrics.success_rate_percent == null ? '—' : `${number(metrics.success_rate_percent, 1)}%`} detail="Based on recorded text-routing events" accent="aic-value--good" />
              <MetricCard label="Fallback events" value={number(metrics.fallback_events)} detail="Automatic provider failovers" />
              <MetricCard label="Average latency" value={metrics.average_latency_ms == null ? '—' : `${number(metrics.average_latency_ms)} ms`} detail="Successful routed completions" />
            </section>

            <section className="aic-provider-grid">
              <article className="aic-panel aic-provider-card aic-provider-card--primary">
                <div className="aic-provider-top"><div><div className="aic-kicker">Primary inference</div><h2>Cloudflare Workers AI</h2></div><StatusPill value={cloudflare.health} /></div>
                <div className="aic-model-name">{cloudflare.model || 'Qwen3-30B-A3B-FP8'}</div>
                <div className="aic-quota-summary"><div><span className="aic-label">Estimated remaining</span><strong>{number(remaining, 2)}</strong><small>Neurons</small></div><div className="aic-quota-used"><span className="aic-label">Used</span><strong>{number(used, 2)}</strong><small>+ {number(reserved, 2)} reserved</small></div></div>
                <div className="aic-quota-track"><div style={{ width: `${quotaPercent}%` }} /></div>
                <div className="aic-quota-foot"><span>{number(used + reserved, 2)} / {number(budget, 0)} Neurons</span><span>{number(quotaPercent, 1)}% used</span></div>
                <p className="aic-footnote">This is Sanctumly's internal ledger, not a live Cloudflare account balance. Usage from the Cloudflare Playground or other applications is not visible here; the provider's own quota response remains authoritative.</p>
                <div className="aic-provider-facts"><div><span>Quota scope</span><strong>Shared by all accounts</strong></div><div><span>Usage date (UTC)</span><strong>{cloudflare.usage_date_utc || '—'}</strong></div><div><span>Daily reset</span><strong>{dateTimeUtc(cloudflare.reset_at_utc)}</strong></div></div>
                {cloudflare.last_error && <div className="aic-provider-error">Last provider error: {cloudflare.last_error}</div>}
              </article>

              <article className="aic-panel aic-provider-card">
                <div className="aic-provider-top"><div><div className="aic-kicker">Reasoning and fallback</div><h2>Groq</h2></div><StatusPill value={groq.health} /></div>
                <div className="aic-model-name">{groq.model || 'openai/gpt-oss-120b'}</div>
                <p className="aic-provider-description">Used for research synthesis, high-complexity requests, manual override and Qwen failover.</p>
                <div className="aic-provider-facts"><div><span>Credentials</span><strong>{groq.configured ? 'Configured' : 'Missing'}</strong></div><div><span>Last recorded request</span><strong>{dateTime(groq.last_event_at)}</strong></div></div>
                <p className="aic-footnote">Status is inferred from the latest recorded Groq request, not an active provider health probe. Provider organization limits still apply.</p>
              </article>

              <article className="aic-panel aic-provider-card">
                <div className="aic-provider-top"><div><div className="aic-kicker">Web research</div><h2>Serper</h2></div><StatusPill value={serper.health} /></div>
                <div className="aic-serper-count">{number(serper.searches_today)} <span>searches today</span></div>
                <p className="aic-provider-description">Search results are synthesized by the reasoning provider. Search availability is separate from inference quota.</p>
                <div className="aic-provider-facts"><div><span>Credentials</span><strong>{serper.configured ? 'Configured' : 'Missing'}</strong></div><div><span>Usage scope</span><strong>Today · UTC</strong></div></div>
              </article>
            </section>

            <section className="aic-panel aic-override-panel">
              <div className="aic-override-copy">
                <div className="aic-kicker">Manual routing control</div>
                <h2>Provider override</h2>
                <p>Temporarily force GPT-OSS for all Sanctumly text requests, or restore automatic routing. The override is global and expires automatically.</p>
                <div className="aic-override-state"><StatusPill value={activeOverride ? 'degraded' : 'available'} /><span>{activeOverride ? `GPT-OSS forced until ${dateTime(data.override.expires_at)}` : 'Automatic routing active · Qwen remains primary'}</span></div>
              </div>
              <div className="aic-override-controls">
                <label><span>Routing mode</span><select value={overrideMode} onChange={event => { overrideModeTouched.current = true; setOverrideMode(event.target.value) }}><option value="auto">Automatic (recommended)</option><option value="groq">Force GPT-OSS-120B</option></select></label>
                <label><span>Override duration</span><select value={duration} onChange={event => setDuration(Number(event.target.value))}><option value={15}>15 minutes</option><option value={30}>30 minutes</option><option value={60}>1 hour</option><option value={120}>2 hours</option><option value={240}>4 hours</option><option value={720}>12 hours</option><option value={1440}>24 hours</option></select></label>
                <button className="aic-button aic-button--primary" onClick={handleOverride} disabled={savingOverride || (overrideMode === 'auto' && !activeOverride)}>
                  {savingOverride ? 'Applying…' : overrideMode === 'groq' ? 'Force GPT-OSS' : 'Restore automatic routing'}
                </button>
              </div>
            </section>

            <div className="aic-section-heading aic-section-heading--standalone"><div><div className="aic-kicker">Usage & distribution</div><h2>Routing analytics</h2></div><span>Last {days} day{days === 1 ? '' : 's'}</span></div>
            <section className="aic-metrics-grid aic-metrics-grid--secondary">
              <MetricCard label="Text requests today" value={number(metrics.text_requests_today)} detail="UTC day · recorded completions" />
              <MetricCard label="Web searches today" value={number(metrics.web_searches_today)} detail="Aggregated across accounts" />
              <MetricCard label="Provider allocation" value="Global" detail="Cloudflare ledger is not per-user" />
              <MetricCard label="Automatic refresh" value="30 sec" detail={data.generated_at ? `Last updated ${time(data.generated_at)}` : '—'} />
            </section>

            <section className="aic-breakdown-grid">
              <Breakdown title="Provider distribution" items={metrics.provider_distribution} />
              <Breakdown title="Routing reasons" items={metrics.routing_reasons} />
              <Breakdown title="Account distribution" items={metrics.account_distribution} />
            </section>

            <section className="aic-panel aic-activity-panel">
              <div className="aic-section-heading"><h2>Recent routing activity</h2><span>Latest 20 events in selected period · no prompts or account IDs</span></div>
              <div className="aic-table-wrap">
                <table className="aic-table">
                  <thead><tr><th>Time</th><th>Provider</th><th>Model</th><th>Route</th><th>Account</th><th>Fallback</th><th>Latency</th><th>Result</th></tr></thead>
                  <tbody>
                    {(data.recent_events || []).length ? data.recent_events.map((event, index) => (
                      <tr key={`${event.timestamp}-${index}`}>
                        <td>{dateTime(event.timestamp)}</td><td><span className="aic-table-provider">{event.provider}</span></td><td className="aic-model-cell">{event.model}</td><td>{event.reason.replaceAll('_', ' ')}</td><td>{event.account_type}</td><td>{event.fallback ? <StatusPill value="cooldown" /> : 'No'}</td><td>{number(event.latency_ms)} ms</td><td><StatusPill value={event.success ? 'available' : 'degraded'} /></td>
                      </tr>
                    )) : <tr><td colSpan="8" className="aic-table-empty">No routing events recorded in this period. New text requests will populate this table.</td></tr>}
                  </tbody>
                </table>
              </div>
            </section>

            <footer className="aic-footer"><span>Sanctumly AI Control Center · Creator-only</span><span>Updated {dateTime(data.generated_at)} · Auto-refresh every 30 seconds</span></footer>
          </>
        ) : !error ? <div className="aic-loading">No telemetry is available yet.</div> : null}
      </main>
    </div>
  )
}
