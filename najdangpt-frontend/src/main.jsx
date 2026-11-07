import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './App.css'
import './theme-refresh.css'

// Keep the app shell in the visual viewport when mobile keyboards are shown.
const syncVisualViewport = () => {
  const viewport = window.visualViewport
  const height = viewport?.height ?? window.innerHeight
  const top = viewport?.offsetTop ?? 0
  document.documentElement.style.setProperty('--app-viewport-height', `${height}px`)
  document.documentElement.style.setProperty('--app-viewport-top', `${top}px`)
}
syncVisualViewport()
window.addEventListener('resize', syncVisualViewport, { passive: true })
window.visualViewport?.addEventListener('resize', syncVisualViewport, { passive: true })
window.visualViewport?.addEventListener('scroll', syncVisualViewport, { passive: true })

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
  const splash = document.getElementById('initial-splash');
  if (splash) {
    splash.classList.add('hide');
    setTimeout(() => splash.remove(), 450); // matches the 0.4s CSS transition
  }
