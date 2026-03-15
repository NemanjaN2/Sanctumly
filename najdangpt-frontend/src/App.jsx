import { useState, useEffect } from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import LoginPage from './pages/LoginPage'
import ChatPage from './pages/ChatPage'
import AdminPanel from './pages/AdminPanel'
import WellnessPage from './pages/WellnessPage'

function App() {
  const [user, setUser] = useState(null)
  const [isAuthenticated, setIsAuthenticated] = useState(false)

  useEffect(() => {
    const saved = localStorage.getItem('najdangpt_user')
    if (saved) { setUser(JSON.parse(saved)); setIsAuthenticated(true) }
  }, [])

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
        <Route path="/" element={<Navigate to="/chat" />} />
      </Routes>
    </Router>
  )
}

export default App
