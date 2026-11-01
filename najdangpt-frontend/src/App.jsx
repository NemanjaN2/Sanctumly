import { useState } from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import LoginPage from './pages/LoginPage'
import ChatPage from './pages/ChatPage'
import AdminPanel from './pages/AdminPanel'
import WellnessPage from './pages/WellnessPage'
import LandingPage from './pages/LandingPage'
import './App.css'

function App() {
  // Init synchronously from localStorage — avoids a one-frame landing flash
  // for logged-in users on hard refresh
  const [user, setUser] = useState(() => {
    try { const s = localStorage.getItem('najdangpt_user'); return s ? JSON.parse(s) : null }
    catch { return null }
  })
  const [isAuthenticated, setIsAuthenticated] = useState(() => !!localStorage.getItem('najdangpt_user'))

  const handleLogin = (userData) => {
    setUser(userData); setIsAuthenticated(true)
    localStorage.setItem('najdangpt_user', JSON.stringify(userData))
  }

  const handleLogout = () => {
    setUser(null); setIsAuthenticated(false)
    localStorage.removeItem('najdangpt_user')
  }

  return (
    <Router>
      <Routes>
        <Route path="/login" element={isAuthenticated ? <Navigate to="/chat" /> : <LoginPage onLogin={handleLogin} />} />
        <Route path="/chat" element={isAuthenticated ? <ChatPage user={user} onLogout={handleLogout} /> : <Navigate to="/login" />} />
        <Route path="/admin" element={isAuthenticated && user?.is_admin ? <AdminPanel user={user} onLogout={handleLogout} /> : <Navigate to="/chat" />} />
        <Route path="/wellness" element={isAuthenticated ? <WellnessPage user={user} /> : <Navigate to="/login" />} />
        <Route path="/" element={isAuthenticated ? <Navigate to="/chat" /> : <LandingPage />} />
      </Routes>
    </Router>
  )
}

export default App
