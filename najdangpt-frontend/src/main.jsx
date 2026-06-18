import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './App.css'

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
