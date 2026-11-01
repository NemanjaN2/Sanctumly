import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import './landing.css'

const CHAT_SCRIPT = [
  { role: 'user', text: 'Ne mogu da spavam poslednjih par noći. Previše razmišljam.' },
  { role: 'ai', text: 'Zvuči iscrpljujuće. Hajde prvo da usporimo — šta ti se najviše vrti po glavi večeras?' },
  { role: 'user', text: 'Posao, uglavnom. Osećam da ne stižem ništa.' },
  { role: 'ai', text: 'To je težak osećaj. Probajmo nešto kratko: vežbu disanja od dva minuta, pa da razmrsimo jedno po jedno.' },
]

const FEATURES = [
  {
    title: 'Na srpskom, prirodno',
    body: 'The first AI wellness companion built for Serbian speakers. No stiff translations — it understands how you actually talk, in Serbian or English.',
  },
  {
    title: 'Mood tracking',
    body: 'Daily check-ins in seconds. See your 7, 30, and 90-day mood history, keep a streak, and notice patterns before they notice you.',
  },
  {
    title: 'Talk it out',
    body: 'Voice conversations with natural Serbian speech. Say it instead of typing it — sometimes that\u2019s the whole point.',
  },
  {
    title: 'Private by design',
    body: 'Your conversations are yours. No ads, no selling your data, no feed algorithms deciding how you should feel.',
  },
]

export default function LandingPage() {
  const [visibleMsgs, setVisibleMsgs] = useState(0)
  const heroRef = useRef(null)

  // Reveal chat messages one by one after mount
  useEffect(() => {
    let i = 0
    const timers = []
    const step = () => {
      i += 1
      setVisibleMsgs(i)
      if (i < CHAT_SCRIPT.length) timers.push(setTimeout(step, 1100))
    }
    timers.push(setTimeout(step, 600))
    return () => timers.forEach(clearTimeout)
  }, [])

  // Scroll reveal for sections
  useEffect(() => {
    const els = document.querySelectorAll('.lp-reveal')
    const io = new IntersectionObserver(
      entries => entries.forEach(e => e.isIntersecting && e.target.classList.add('in')),
      { threshold: 0.15 }
    )
    els.forEach(el => io.observe(el))
    return () => io.disconnect()
  }, [])

  return (
    <div className="lp">
      {/* Nav */}
      <nav className="lp-nav">
        <div className="lp-nav-inner">
          <a className="lp-brand" href="/">
            <img src="/logo.png" alt="" />
            <span>Sanctumly</span>
          </a>
          <div className="lp-nav-actions">
            <Link to="/login" className="lp-nav-login">Log in</Link>
            <Link to="/login" className="lp-btn lp-btn-sm">Get started</Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <header className="lp-hero" ref={heroRef}>
        <div className="lp-breath" aria-hidden="true" />
        <div className="lp-hero-inner">
          <div className="lp-hero-copy">
            <div className="lp-eyebrow">Prva srpska AI wellness platforma</div>
            <h1 className="lp-h1">
              A calmer mind,<br />
              <em>in your own language.</em>
            </h1>
            <p className="lp-lede">
              Sanctumly is an AI wellness companion that speaks Serbian natively.
              Talk through what&rsquo;s on your mind, track your mood, and build
              steadier days — in Serbian or English, on any device.
            </p>
            <div className="lp-cta-row">
              <Link to="/login" className="lp-btn">Start free</Link>
              <Link to="/login" className="lp-btn-ghost">I already have an account</Link>
            </div>
            <div className="lp-platforms" aria-label="Available platforms">
              <span>Web</span><i /><span>iOS</span><i /><span>macOS</span><i /><span>Android</span>
            </div>
          </div>

          {/* Live chat preview */}
          <div className="lp-demo" aria-hidden="true">
            <div className="lp-demo-bar">
              <img src="/logo.png" alt="" />
              <div>
                <div className="lp-demo-name">Sanctumly</div>
                <div className="lp-demo-status"><i />online</div>
              </div>
            </div>
            <div className="lp-demo-msgs">
              {CHAT_SCRIPT.slice(0, visibleMsgs).map((m, idx) => (
                <div key={idx} className={`lp-msg ${m.role}`}>{m.text}</div>
              ))}
              {visibleMsgs < CHAT_SCRIPT.length && (
                <div className="lp-msg ai lp-typing"><span /><span /><span /></div>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Features */}
      <section className="lp-section lp-reveal">
        <div className="lp-section-head">
          <h2 className="lp-h2">Built for how you actually feel</h2>
          <p className="lp-sub">Ne &ldquo;kako ste danas&rdquo; — nego stvarno.</p>
        </div>
        <div className="lp-grid">
          {FEATURES.map(f => (
            <div key={f.title} className="lp-card">
              <h3>{f.title}</h3>
              <p>{f.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Mood strip */}
      <section className="lp-section lp-reveal">
        <div className="lp-mood">
          <div className="lp-mood-copy">
            <h2 className="lp-h2">Your mood, made visible</h2>
            <p className="lp-sub">
              A 10-second daily check-in turns into a picture of your month.
              Streaks keep you honest; patterns keep you informed.
            </p>
          </div>
          <div className="lp-mood-chart" aria-hidden="true">
            {[3, 2, 4, 3, 5, 4, 2, 3, 4, 5, 4, 5, 3, 4].map((v, i) => (
              <div key={i} className="lp-mood-bar" style={{ height: `${v * 20}%`, animationDelay: `${i * 60}ms` }} />
            ))}
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="lp-section lp-final lp-reveal">
        <h2 className="lp-h1 lp-final-h"><em>Počni danas.</em></h2>
        <p className="lp-lede">Free to use. Works everywhere. Speaks your language.</p>
        <Link to="/login" className="lp-btn lp-btn-lg">Create your account</Link>
      </section>

      {/* Footer */}
      <footer className="lp-footer">
        <div className="lp-footer-inner">
          <div className="lp-brand lp-brand-dim">
            <img src="/logo.png" alt="" />
            <span>Sanctumly</span>
          </div>
          <div className="lp-footer-note">
            Sanctumly is a wellness companion, not a substitute for professional care.
            If you&rsquo;re in crisis, contact local emergency services.
          </div>
          <div className="lp-footer-meta">© {new Date().getFullYear()} Sanctumly · Belgrade</div>
        </div>
      </footer>
    </div>
  )
}
