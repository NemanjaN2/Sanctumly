import { useState, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { sendMessage, clearChat, submitFeedback } from '../api/chat'
import { uploadDocument } from '../api/upload'

import { marked } from 'marked'

export default function ChatPage({ user, onLogout }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [personality, setPersonality] = useState('default')
  const [sessionId] = useState(() => {
    const stored = localStorage.getItem('session_id')
    if (stored) {
      console.log('🔒 Using secure session from localStorage')
      return stored
    }
    console.warn('⚠️ No secure session found, generating fallback')
    return `session_${Date.now()}`
  })
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [uploadedFiles, setUploadedFiles] = useState([])
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [messageFeedback, setMessageFeedback] = useState({})
  const [speakingMessageIndex, setSpeakingMessageIndex] = useState(null)
  const [ttsLanguage, setTtsLanguage] = useState('en-US')
  const [showInstallPrompt, setShowInstallPrompt] = useState(false)
  const [deferredPrompt, setDeferredPrompt] = useState(null)
  const [isRecording, setIsRecording] = useState(false)
  const [mediaRecorder, setMediaRecorder] = useState(null)
  const [voiceMode, setVoiceMode] = useState(false)
  const [voiceState, setVoiceState] = useState('idle')
  const [showDownloadModal, setShowDownloadModal] = useState(false)
  const [pendingImage, setPendingImage] = useState(null) // { file, preview, base64 }
  const messagesEndRef = useRef(null)
  const fileInputRef = useRef(null)
  const imageInputRef = useRef(null)
  const currentAudioRef = useRef(null)

  const personalities = [
    { value: 'default', label: 'Default', description: 'Balanced assistant' },
    { value: 'therapist', label: 'Wellness Companion', description: 'Mental health support' },
  ]

  if (user.is_creator) {
    personalities.push({ 
      value: 'hacker', 
      label: 'Cybersecurity Agent',
      description: 'Pentesting & Hacking'
    })
  }

  const suggestionPrompts = [
    { text: 'Help me brainstorm ideas', prompt: 'Help me brainstorm creative ideas for my project' },
    { text: 'Explain a concept', prompt: 'Explain quantum computing in simple terms' },
    { text: 'Analyze my document', prompt: 'Analyze the document I uploaded and summarize key points' },
    { text: 'Write some code', prompt: 'Write a Python script to process CSV files' },
  ]

  useEffect(() => {
    if (sidebarOpen) {
      document.body.classList.add('sidebar-open')
    } else {
      document.body.classList.remove('sidebar-open')
    }
    return () => document.body.classList.remove('sidebar-open')
  }, [sidebarOpen])

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  useEffect(() => {
    if (error) {
      const timer = setTimeout(() => setError(''), 5000)
      return () => clearTimeout(timer)
    }
  }, [error])

  useEffect(() => {
    if (success) {
      const timer = setTimeout(() => setSuccess(''), 3000)
      return () => clearTimeout(timer)
    }
  }, [success])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  // Image handling
  const handleImageSelect = (event) => {
    const file = event.target.files[0]
    if (!file) return

    if (!file.type.startsWith('image/')) {
      setError('Please select an image file')
      return
    }

    if (file.size > 4 * 1024 * 1024) {
      setError('Image too large. Maximum 4MB.')
      return
    }

    const preview = URL.createObjectURL(file)

    // Convert to base64
    const reader = new FileReader()
    reader.onload = (e) => {
      // Strip the data:image/...;base64, prefix — send raw base64
      const base64Full = e.target.result
      const base64Raw = base64Full.split(',')[1]
      setPendingImage({ file, preview, base64: base64Raw })
    }
    reader.readAsDataURL(file)

    // Reset input so same file can be selected again
    if (imageInputRef.current) {
      imageInputRef.current.value = ''
    }
  }

  const removePendingImage = () => {
    if (pendingImage?.preview) {
      URL.revokeObjectURL(pendingImage.preview)
    }
    setPendingImage(null)
  }

  const handleSend = async (messageText = null) => {
    const textToSend = messageText || input
    if ((!textToSend.trim() && !pendingImage) || loading) return

    const displayContent = pendingImage ? `📷 ${textToSend || 'Analyze this image'}` : textToSend
    const actualMessage = textToSend.trim() || (pendingImage ? 'What do you see in this image? Describe and analyze it.' : '')

    const imageBase64 = pendingImage?.base64 || null

    const userMessage = {
      role: 'user',
      content: displayContent,
      timestamp: new Date().toISOString(),
      imagePreview: pendingImage?.preview || null,
    }

    setMessages((prev) => [...prev, userMessage])
    setInput('')
    removePendingImage()
    setLoading(true)
    setError('')

    try {
      const response = await sendMessage(actualMessage, sessionId, user.username, personality, imageBase64)
      
      const assistantMessage = {
        role: 'assistant',
        content: response.response,
        timestamp: new Date().toISOString(),
      }

      setMessages((prev) => [...prev, assistantMessage])
    } catch (err) {
      console.error('Failed to send message:', err)
      setError('Failed to send message. Please try again.')
      
      const errorMessage = {
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
        timestamp: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, errorMessage])
    } finally {
      setLoading(false)
    }
  }

  const handleSuggestionClick = (prompt) => {
    handleSend(prompt)
  }

  const handleClearChat = async () => {
    if (confirm('Clear all messages? This cannot be undone.')) {
      try {
        await clearChat(sessionId)
        setMessages([])
        setSuccess('Chat cleared successfully')
      } catch (err) {
        console.error('Failed to clear chat:', err)
        setError('Failed to clear chat. Please try again.')
      }
    }
  }

  const handleFileUpload = async (event) => {
    const file = event.target.files[0]
    if (!file) return

    if (file.size > 20 * 1024 * 1024) {
      setError('File too large. Maximum size is 20MB.')
      return
    }

    setUploading(true)
    setUploadProgress(0)
    setError('')

    const progressInterval = setInterval(() => {
      setUploadProgress(prev => {
        if (prev >= 90) {
          clearInterval(progressInterval)
          return 90
        }
        return prev + 10
      })
    }, 200)

    try {
      const result = await uploadDocument(file, sessionId)
      clearInterval(progressInterval)
      setUploadProgress(100)
      
      setUploadedFiles(prev => [...prev, result.filename])
      setSuccess(`Uploaded ${result.filename}`)
      
      setTimeout(() => {
        setUploadProgress(0)
      }, 1000)
    } catch (err) {
      clearInterval(progressInterval)
      console.error('Upload failed:', err)
      setError(`Failed to upload ${file.name}. Please try again.`)
      setUploadProgress(0)
    } finally {
      setUploading(false)
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    }
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handlePersonalityChange = (value) => {
    setPersonality(value)
    setSidebarOpen(false)
    const selected = personalities.find(p => p.value === value)
    setSuccess(`Switched to ${selected?.label}`)
  }

  const handleFeedback = async (messageIndex, feedbackType) => {
    setMessageFeedback(prev => ({
      ...prev,
      [messageIndex]: feedbackType
    }))

    try {
      const message = messages[messageIndex]
      await submitFeedback(message.content, feedbackType, sessionId, user.username)
      setSuccess('Feedback recorded')
    } catch (err) {
      console.error('Failed to submit feedback:', err)
    }
  }

  const handleCopyMessage = (content) => {
    navigator.clipboard.writeText(content)
    setSuccess('Copied to clipboard')
  }

  const handleReadAloud = async (messageIndex, content) => {
    if (currentAudioRef.current) {
      currentAudioRef.current.pause()
      currentAudioRef.current = null
    }

    if (speakingMessageIndex === messageIndex) {
      setSpeakingMessageIndex(null)
      return
    }

    setSpeakingMessageIndex(messageIndex)

    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL || 'https://sanctumly-production.up.railway.app'}/speech/tts`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          text: content,
          language: ttsLanguage,
          voice_gender: 'female'
        })
      })

      if (!response.ok) {
        throw new Error('TTS request failed')
      }

      const data = await response.json()
      
      const audioBlob = new Blob(
        [Uint8Array.from(atob(data.audio), c => c.charCodeAt(0))],
        { type: 'audio/mp3' }
      )
      const audioUrl = URL.createObjectURL(audioBlob)
      const audio = new Audio(audioUrl)
      
      currentAudioRef.current = audio

      audio.onended = () => {
        setSpeakingMessageIndex(null)
        URL.revokeObjectURL(audioUrl)
        currentAudioRef.current = null
      }

      audio.onerror = () => {
        setSpeakingMessageIndex(null)
        setError('Failed to play audio')
        currentAudioRef.current = null
      }

      audio.play()

    } catch (err) {
      console.error('TTS error:', err)
      setSpeakingMessageIndex(null)
      setError('Failed to read aloud')
    }
  }

  useEffect(() => {
    return () => {
      if (currentAudioRef.current) {
        currentAudioRef.current.pause()
        currentAudioRef.current = null
      }
    }
  }, [])

  useEffect(() => {
    const handler = (e) => {
      e.preventDefault()
      setDeferredPrompt(e)
      setShowInstallPrompt(true)
    }
    
    window.addEventListener('beforeinstallprompt', handler)
    
    window.addEventListener('appinstalled', () => {
      setShowInstallPrompt(false)
      setSuccess('App installed successfully')
    })
    
    return () => {
      window.removeEventListener('beforeinstallprompt', handler)
    }
  }, [])

  const handleInstallClick = async () => {
    if (!deferredPrompt) return
    
    deferredPrompt.prompt()
    const { outcome } = await deferredPrompt.userChoice
    
    if (outcome === 'accepted') {
      setSuccess('Installing app...')
    }
    
    setDeferredPrompt(null)
    setShowInstallPrompt(false)
  }

  const handleVoiceClick = async () => {
    if (isRecording) {
      if (mediaRecorder) {
        mediaRecorder.stop()
      }
    } else {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
        const recorder = new MediaRecorder(stream, {
          mimeType: 'audio/webm'
        })
        
        const audioChunks = []
        
        recorder.ondataavailable = (event) => {
          audioChunks.push(event.data)
        }
        
        recorder.onstop = async () => {
          const audioBlob = new Blob(audioChunks, { type: 'audio/webm' })
          stream.getTracks().forEach(track => track.stop())
          await transcribeAudio(audioBlob)
        }
        
        recorder.start()
        setMediaRecorder(recorder)
        setIsRecording(true)
        setSuccess('Recording...')
      } catch (err) {
        console.error('Microphone error:', err)
        setError('Microphone access denied')
      }
    }
  }

  const transcribeAudio = async (audioBlob) => {
    try {
      setLoading(true)
      
      const formData = new FormData()
      formData.append('file', audioBlob, 'audio.webm')
      
      const response = await fetch(`${import.meta.env.VITE_API_URL || 'https://sanctumly-production.up.railway.app'}/speech/transcribe`, {
        method: 'POST',
        body: formData
      })
      
      if (!response.ok) {
        throw new Error('Transcription failed')
      }
      
      const data = await response.json()
      
      if (data.success && data.transcript) {
        setInput(data.transcript)
        setSuccess('Transcribed')
      } else {
        setError('No speech detected')
      }
    } catch (err) {
      console.error('Transcription error:', err)
      setError('Transcription failed')
    } finally {
      setLoading(false)
      setIsRecording(false)
      setMediaRecorder(null)
    }
  }

  // Voice Conversation Mode Functions
  const startVoiceMode = () => {
    setVoiceMode(true)
    setVoiceState('idle')
  }

  const stopVoiceMode = () => {
    setVoiceMode(false)
    setVoiceState('idle')
    if (mediaRecorder) {
      mediaRecorder.stop()
    }
    if (currentAudioRef.current) {
      currentAudioRef.current.pause()
      currentAudioRef.current = null
    }
    setSpeakingMessageIndex(null)
  }

  const startVoiceRecording = async () => {
    if (!voiceMode) return
    
    try {
      setVoiceState('listening')
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      
      let mimeType = 'audio/webm'
      if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
        mimeType = 'audio/webm;codecs=opus'
      } else if (MediaRecorder.isTypeSupported('audio/mp4')) {
        mimeType = 'audio/mp4'
      }
      
      const recorder = new MediaRecorder(stream, { mimeType })
      
      const audioChunks = []
      
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunks.push(event.data)
        }
      }
      
      recorder.onstop = async () => {
        stream.getTracks().forEach(track => track.stop())
        
        if (audioChunks.length === 0) {
          setError('No audio recorded')
          setVoiceState('idle')
          return
        }
        
        const audioBlob = new Blob(audioChunks, { type: mimeType })
        
        if (audioBlob.size < 1000) {
          setError('Recording too short - hold longer')
          setVoiceState('idle')
          return
        }
        
        await processVoiceInput(audioBlob)
      }
      
      recorder.start(250)
      setMediaRecorder(recorder)
    } catch (err) {
      console.error('Microphone error:', err)
      setError('Microphone access denied')
      setVoiceState('idle')
    }
  }

  const stopVoiceRecording = () => {
    if (mediaRecorder && mediaRecorder.state === 'recording') {
      mediaRecorder.stop()
      setMediaRecorder(null)
    }
  }

  const processVoiceInput = async (audioBlob) => {
    try {
      setVoiceState('thinking')
      
      const formData = new FormData()
      const extension = audioBlob.type.includes('mp4') ? 'mp4' : 'webm'
      formData.append('file', audioBlob, `audio.${extension}`)
      
      const transcribeResponse = await fetch(`${import.meta.env.VITE_API_URL || 'https://sanctumly-production.up.railway.app'}/speech/transcribe`, {
        method: 'POST',
        body: formData
      })
      
      if (!transcribeResponse.ok) {
        throw new Error('Transcription failed')
      }
      
      const transcribeData = await transcribeResponse.json()
      
      if (!transcribeData.success || !transcribeData.transcript) {
        setError('No speech detected - try speaking louder')
        setVoiceState('idle')
        return
      }
      
      const userText = transcribeData.transcript
      
      const userMessage = {
        role: 'user',
        content: userText,
        timestamp: new Date().toISOString(),
      }
      setMessages(prev => [...prev, userMessage])
      
      const chatResponse = await sendMessage(userText, sessionId, user.username, personality)
      
      const assistantMessage = {
        role: 'assistant',
        content: chatResponse.response,
        timestamp: new Date().toISOString(),
      }
      setMessages(prev => [...prev, assistantMessage])
      
      setVoiceState('speaking')
      await speakResponse(chatResponse.response)
      
    } catch (err) {
      console.error('Voice processing error:', err)
      setError('Voice processing failed')
      setVoiceState('idle')
    }
  }

  const speakResponse = async (text) => {
    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL || 'https://sanctumly-production.up.railway.app'}/speech/tts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: text,
          language: ttsLanguage,
          voice_gender: 'female'
        })
      })
      
      if (!response.ok) throw new Error('TTS failed')
      
      const data = await response.json()
      
      const audioBlob = new Blob(
        [Uint8Array.from(atob(data.audio), c => c.charCodeAt(0))],
        { type: 'audio/mp3' }
      )
      const audioUrl = URL.createObjectURL(audioBlob)
      const audio = new Audio(audioUrl)
      
      currentAudioRef.current = audio
      
      audio.onended = () => {
        URL.revokeObjectURL(audioUrl)
        currentAudioRef.current = null
        if (voiceMode) {
          setVoiceState('idle')
        }
      }
      
      audio.onerror = () => {
        setVoiceState('idle')
        setError('Audio playback failed')
      }
      
      await audio.play()
      
    } catch (err) {
      console.error('TTS error:', err)
      setVoiceState('idle')
    }
  }

  // Handle paste for images
  useEffect(() => {
    const handlePaste = (e) => {
      const items = e.clipboardData?.items
      if (!items) return

      for (const item of items) {
        if (item.type.startsWith('image/')) {
          e.preventDefault()
          const file = item.getAsFile()
          if (file) {
            const preview = URL.createObjectURL(file)
            const reader = new FileReader()
            reader.onload = (ev) => {
              const base64Raw = ev.target.result.split(',')[1]
              setPendingImage({ file, preview, base64: base64Raw })
              setSuccess('Image pasted')
            }
            reader.readAsDataURL(file)
          }
          break
        }
      }
    }

    window.addEventListener('paste', handlePaste)
    return () => window.removeEventListener('paste', handlePaste)
  }, [])

  const currentPersonality = personalities.find(p => p.value === personality)

  return (
    <div className="flex h-screen">
      {sidebarOpen && (
        <div 
          className="sidebar-overlay"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <div className={`sidebar ${sidebarOpen ? 'sidebar-open' : ''}`}>
        <div className="sidebar-header">
          <div className="sidebar-title">
            Sanctumly
          </div>
          <button 
            onClick={() => setSidebarOpen(false)}
            className="sidebar-close"
            aria-label="Close menu"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>

        <div className="sidebar-content">
          <div className="sidebar-section">
            <div className="sidebar-section-title">Account</div>
            <div style={{ 
              padding: '0.625rem 0.75rem',
              background: 'rgba(139, 92, 246, 0.08)',
              borderRadius: '0.5rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem'
            }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 500, fontSize: '0.875rem', color: 'var(--text-primary)' }}>
                  {user.username}
                </div>
                {user.is_creator && (
                  <div className="user-badge" style={{ marginTop: '0.25rem' }}>
                    Creator
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="sidebar-section">
            <div className="sidebar-section-title">AI Agents</div>
            <div>
              {personalities.map((p) => (
                <button
                  key={p.value}
                  onClick={() => handlePersonalityChange(p.value)}
                  className={`agent-button ${personality === p.value ? 'agent-button-active' : ''}`}
                >
                  <span className="agent-label">{p.label}</span>
                  {personality === p.value && (
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <polyline points="20 6 9 17 4 12"></polyline>
                    </svg>
                  )}
                </button>
              ))}
            </div>
          </div>

          <div className="sidebar-section">
            <div className="sidebar-section-title">Actions</div>
            {user.is_admin && (
              <Link to="/admin" className="sidebar-link">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="3"></circle>
                  <path d="M12 1v6m0 6v6m6-11.66l-5.2 3m-1.6 2.76l-5.2 3M6.34 6.34l5.2 3m1.6 2.76l5.2 3M1 12h6m6 0h6"></path>
                </svg>
                Admin Panel
              </Link>
            )}
            <a href="/wellness" className="sidebar-link" style={{ textDecoration: "none" }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path>
              </svg>
              My Wellness
            </a>
            <button onClick={handleClearChat} className="sidebar-link">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="3 6 5 6 21 6"></polyline>
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
              </svg>
              Clear Chat
            </button>
            <button onClick={() => setShowDownloadModal(true)} className="sidebar-link">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                <polyline points="7 10 12 15 17 10"/>
                <line x1="12" y1="15" x2="12" y2="3"/>
              </svg>
              Download Apps
            </button>
            <button onClick={onLogout} className="sidebar-link sidebar-link-danger">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                <polyline points="16 17 21 12 16 7"></polyline>
                <line x1="21" y1="12" x2="9" y2="12"></line>
              </svg>
              Logout
            </button>
          </div>
        </div>
      </div>

      <div className="flex-1 flex flex-col" style={{ maxWidth: '100%', margin: '0 auto' }}>
        {/* Header */}
        <div className="glass-heavy" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
          <div style={{
            maxWidth: '800px',
            margin: '0 auto',
            padding: '0.875rem 1.5rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
              <button 
                onClick={() => setSidebarOpen(true)}
                className="hamburger-button"
                aria-label="Open menu"
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="3" y1="12" x2="21" y2="12"></line>
                  <line x1="3" y1="6" x2="21" y2="6"></line>
                  <line x1="3" y1="18" x2="21" y2="18"></line>
                </svg>
              </button>
              <h1 style={{ fontSize: '1.125rem', fontWeight: 600 }} className="gradient-text">Sanctumly</h1>
              <div style={{ 
                fontSize: '0.8125rem', 
                color: 'var(--text-tertiary)',
                display: 'none'
              }} className="sm:block">
                {currentPersonality?.label}
              </div>
            </div>
            
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <button
                onClick={() => setTtsLanguage(prev => prev === 'en-US' ? 'sr-RS' : 'en-US')}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.375rem',
                  padding: '0.375rem 0.625rem',
                  background: 'var(--bg-tertiary)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: '0.375rem',
                  cursor: 'pointer',
                  transition: 'all 0.2s'
                }}
                title={ttsLanguage === 'sr-RS' ? 'TTS: Serbian' : 'TTS: English'}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={ttsLanguage === 'sr-RS' ? '#ffd700' : 'var(--text-secondary)'} strokeWidth="2">
                  <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
                  <path d="M15.54 8.46a5 5 0 0 1 0 7.07"/>
                  <path d="M19.07 4.93a10 10 0 0 1 0 14.14"/>
                </svg>
                <span style={{ 
                  fontSize: '0.75rem', 
                  fontWeight: 600,
                  color: ttsLanguage === 'sr-RS' ? '#ffd700' : 'var(--text-secondary)'
                }}>
                  {ttsLanguage === 'sr-RS' ? 'SR' : 'EN'}
                </span>
              </button>

              <button
                onClick={startVoiceMode}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.375rem',
                  padding: '0.375rem 0.625rem',
                  background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                  border: 'none',
                  borderRadius: '0.375rem',
                  cursor: 'pointer',
                  transition: 'all 0.2s'
                }}
                title="Start voice conversation"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2">
                  <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
                  <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
                  <line x1="12" y1="19" x2="12" y2="23"/>
                  <line x1="8" y1="23" x2="16" y2="23"/>
                </svg>
                <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'white' }}>
                  Voice
                </span>
              </button>
            </div>
          </div>
        </div>

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto" style={{ padding: '2rem 1.5rem' }}>
          <div style={{ maxWidth: '800px', margin: '0 auto', width: '100%' }}>
            {error && (
              <div className="error-message" style={{ marginBottom: '1rem' }}>
                <span>{error}</span>
              </div>
            )}

            {success && (
              <div className="success-message" style={{ marginBottom: '1rem' }}>
                <span>{success}</span>
              </div>
            )}

            {messages.length === 0 ? (
              <div className="empty-state">
                <img 
                  src="/logo.png" 
                  alt="Sanctumly" 
                  className="empty-state-icon"
                  style={{ 
                    height: '80px',
                    width: 'auto',
                    objectFit: 'contain',
                    marginBottom: '1.5rem',
                    filter: 'drop-shadow(0 0 20px rgba(139, 92, 246, 0.3))'
                  }}
                />
                <h2 className="empty-state-title">Welcome to Sanctumly</h2>
                <p className="empty-state-subtitle">
                  Start a conversation or try one of these suggestions
                </p>
                <div className="empty-state-suggestions">
                  {suggestionPrompts.map((suggestion, idx) => (
                    <div
                      key={idx}
                      className="suggestion-card"
                      onClick={() => handleSuggestionClick(suggestion.prompt)}
                    >
                      <div className="suggestion-text">{suggestion.text}</div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                {messages.map((msg, idx) => (
                  <div
                    key={idx}
                    style={{ 
                      display: 'flex',
                      justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start'
                    }}
                  >
                    <div className={`message ${msg.role === 'user' ? 'message-user' : 'message-assistant'}`}>
                      {/* Show image preview if user message had an image */}
                      {msg.imagePreview && (
                        <div style={{ marginBottom: '0.5rem' }}>
                          <img 
                            src={msg.imagePreview} 
                            alt="Uploaded" 
                            style={{ 
                              maxWidth: '200px', 
                              maxHeight: '200px', 
                              borderRadius: '0.5rem',
                              border: '1px solid rgba(255,255,255,0.1)'
                            }} 
                          />
                        </div>
                      )}
                      {msg.role === 'assistant' ? (
                        <div 
                          className="markdown-content"
                          dangerouslySetInnerHTML={{ __html: marked(msg.content) }}
                        />
                      ) : (
                        <div style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</div>
                      )}
                      <div style={{ 
                        display: 'flex', 
                        alignItems: 'center', 
                        justifyContent: 'space-between', 
                        marginTop: '0.5rem',
                        gap: '0.5rem'
                      }}>
                        <div style={{ fontSize: '0.75rem', opacity: 0.5 }}>
                          {new Date(msg.timestamp).toLocaleTimeString()}
                        </div>
                        
                        {msg.role === 'assistant' && (
                          <div style={{ display: 'flex', gap: '0.25rem' }}>
                            <button
                              onClick={() => handleCopyMessage(msg.content)}
                              className="feedback-btn tooltip"
                              data-tooltip="Copy"
                              aria-label="Copy message"
                            >
                              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                              </svg>
                            </button>
                            
                            <button
                              onClick={() => handleReadAloud(idx, msg.content)}
                              className={`feedback-btn tooltip ${speakingMessageIndex === idx ? 'feedback-active' : ''}`}
                              data-tooltip={speakingMessageIndex === idx ? 'Stop' : 'Read aloud'}
                              aria-label="Read aloud"
                            >
                              {speakingMessageIndex === idx ? (
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" strokeWidth="2">
                                  <rect x="6" y="4" width="4" height="16"></rect>
                                  <rect x="14" y="4" width="4" height="16"></rect>
                                </svg>
                              ) : (
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                  <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon>
                                  <path d="M15.54 8.46a5 5 0 0 1 0 7.07"></path>
                                </svg>
                              )}
                            </button>
                            
                            <button
                              onClick={() => handleFeedback(idx, 'like')}
                              className={`feedback-btn tooltip ${messageFeedback[idx] === 'like' ? 'feedback-active' : ''}`}
                              data-tooltip="Good"
                              aria-label="Like"
                            >
                              <svg width="14" height="14" viewBox="0 0 24 24" fill={messageFeedback[idx] === 'like' ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2">
                                <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"></path>
                              </svg>
                            </button>
                            
                            <button
                              onClick={() => handleFeedback(idx, 'dislike')}
                              className={`feedback-btn tooltip ${messageFeedback[idx] === 'dislike' ? 'feedback-active' : ''}`}
                              data-tooltip="Bad"
                              aria-label="Dislike"
                            >
                              <svg width="14" height="14" viewBox="0 0 24 24" fill={messageFeedback[idx] === 'dislike' ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2">
                                <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"></path>
                              </svg>
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                ))}

                {loading && (
                  <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
                    <div className="message message-assistant">
                      <div className="typing-indicator">
                        <div className="typing-dot"></div>
                        <div className="typing-dot"></div>
                        <div className="typing-dot"></div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Input Area */}
        <div className="glass-heavy" style={{ 
          borderTop: '1px solid var(--border-subtle)',
          padding: '1rem 1.5rem'
        }}>
          <div style={{ maxWidth: '800px', margin: '0 auto', width: '100%' }}>
            {uploadedFiles.length > 0 && (
              <div style={{ marginBottom: '0.75rem', fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                {uploadedFiles.length} document(s) uploaded
              </div>
            )}

            {uploading && uploadProgress > 0 && (
              <div className="upload-progress" style={{ marginBottom: '0.75rem' }}>
                <div className="progress-bar">
                  <div className="progress-fill" style={{ width: `${uploadProgress}%` }} />
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
                  Uploading... {uploadProgress}%
                </div>
              </div>
            )}

            {/* Pending image preview */}
            {pendingImage && (
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.75rem',
                padding: '0.5rem 0.75rem',
                marginBottom: '0.75rem',
                background: 'rgba(102, 126, 234, 0.1)',
                borderRadius: '0.5rem',
                border: '1px solid rgba(102, 126, 234, 0.2)'
              }}>
                <img 
                  src={pendingImage.preview} 
                  alt="Preview" 
                  style={{ 
                    width: '48px', 
                    height: '48px', 
                    objectFit: 'cover', 
                    borderRadius: '0.375rem',
                    border: '1px solid rgba(255,255,255,0.1)'
                  }} 
                />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: '0.8125rem', fontWeight: 500, color: 'var(--text-primary)' }}>
                    Image attached
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                    Will be analyzed with your message
                  </div>
                </div>
                <button
                  onClick={removePendingImage}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: 'var(--text-secondary)',
                    cursor: 'pointer',
                    padding: '0.25rem'
                  }}
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <line x1="18" y1="6" x2="6" y2="18"/>
                    <line x1="6" y1="6" x2="18" y2="18"/>
                  </svg>
                </button>
              </div>
            )}

            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-end' }}>
              {/* Hidden file inputs */}
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileUpload}
                accept=".txt,.pdf,.docx,.xlsx,.xls,.csv,.epub"
                style={{ display: 'none' }}
              />
              <input
                type="file"
                ref={imageInputRef}
                onChange={handleImageSelect}
                accept="image/*"
                style={{ display: 'none' }}
              />
              
              {/* Attach file button */}
              <button 
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
                className="btn btn-secondary btn-icon tooltip"
                data-tooltip="Attach file"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/>
                </svg>
              </button>

              {/* Image upload button */}
              <button
                onClick={() => imageInputRef.current?.click()}
                className="btn btn-secondary btn-icon tooltip"
                data-tooltip="Attach image"
                disabled={loading}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                  <circle cx="8.5" cy="8.5" r="1.5"/>
                  <polyline points="21 15 16 10 5 21"/>
                </svg>
              </button>

              <div style={{ flex: 1, position: 'relative' }}>
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder={pendingImage ? "Describe what to analyze..." : "Message Sanctumly..."}
                  className="input"
                  rows="1"
                  disabled={loading}
                  style={{
                    minHeight: '44px',
                    maxHeight: '200px',
                    paddingRight: '3rem',
                    resize: 'none'
                  }}
                />
                <button
                  onClick={() => handleSend()}
                  disabled={loading || (!input.trim() && !pendingImage)}
                  className="btn btn-primary"
                  style={{
                    position: 'absolute',
                    right: '4px',
                    bottom: '4px',
                    minWidth: '36px',
                    height: '36px',
                    padding: '0.5rem',
                    borderRadius: '0.375rem'
                  }}
                >
                  {loading ? (
                    <div style={{ width: '18px', height: '18px' }}>...</div>
                  ) : (
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <line x1="22" y1="2" x2="11" y2="13"></line>
                      <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                    </svg>
                  )}
                </button>
              </div>

              <button 
                onClick={handleVoiceClick}
                className={`btn ${isRecording ? 'btn-primary' : 'btn-secondary'} btn-icon tooltip`}
                data-tooltip={isRecording ? 'Stop' : 'Voice input'}
                disabled={loading}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{
                  animation: isRecording ? 'pulse 1s infinite' : 'none'
                }}>
                  <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path>
                  <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
                  <line x1="12" y1="19" x2="12" y2="23"></line>
                  <line x1="8" y1="23" x2="16" y2="23"></line>
                </svg>
              </button>
            </div>

            <div style={{
              marginTop: '0.75rem',
              textAlign: 'center',
              fontSize: '0.6875rem',
              color: 'var(--text-tertiary)',
              opacity: 0.7
            }}>
              Sanctumly can make mistakes and cannot replace a real therapist.
            </div>
          </div>
        </div>

        {/* PWA Install Prompt */}
        {showInstallPrompt && (
          <div style={{ 
            position: 'fixed', bottom: '100px', left: '50%', transform: 'translateX(-50%)',
            zIndex: 1000, animation: 'fadeIn 0.3s ease'
          }}>
            <div style={{
              background: 'rgba(139, 92, 246, 0.95)', backdropFilter: 'blur(12px)',
              padding: '1rem 1.5rem', borderRadius: '0.75rem',
              boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)',
              display: 'flex', alignItems: 'center', gap: '1rem', maxWidth: '90vw'
            }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, marginBottom: '0.25rem' }}>Install Sanctumly</div>
                <div style={{ fontSize: '0.875rem', opacity: 0.9 }}>Get the app for faster access</div>
              </div>
              <button onClick={handleInstallClick} className="btn btn-primary" style={{ padding: '0.5rem 1rem', whiteSpace: 'nowrap' }}>Install</button>
              <button onClick={() => setShowInstallPrompt(false)} className="btn btn-secondary" style={{ padding: '0.5rem', minWidth: 'auto' }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
              </button>
            </div>
          </div>
        )}

        {/* Download Apps Modal */}
        {showDownloadModal && (
          <div 
            style={{
              position: 'fixed', inset: 0, background: 'rgba(0, 0, 0, 0.6)',
              backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center',
              justifyContent: 'center', zIndex: 1000, padding: '1rem'
            }}
            onClick={() => setShowDownloadModal(false)}
          >
            <div 
              style={{
                background: 'var(--bg-secondary, #1a1a2e)', borderRadius: '0.75rem',
                maxWidth: '420px', width: '100%', maxHeight: '90vh', overflow: 'auto',
                border: '1px solid var(--border-color, rgba(255,255,255,0.1))'
              }}
              onClick={(e) => e.stopPropagation()}
            >
              <div style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '1rem 1.25rem', borderBottom: '1px solid var(--border-color, rgba(255,255,255,0.1))'
              }}>
                <h2 style={{ fontSize: '1.125rem', fontWeight: 600, color: 'var(--text-primary, #fff)' }}>Download Apps</h2>
                <button onClick={() => setShowDownloadModal(false)} style={{ background: 'transparent', border: 'none', color: 'var(--text-secondary, #888)', cursor: 'pointer', padding: '0.25rem' }}>
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                </button>
              </div>

              <div style={{ padding: '1.25rem' }}>
                <a href="https://storage.googleapis.com/najdangpt-downloads/Sanctumly.app.zip" download style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '0.875rem', background: 'var(--bg-primary, #0d0d1a)', borderRadius: '0.5rem', textDecoration: 'none', marginBottom: '0.75rem' }}>
                  <div style={{ width: '40px', height: '40px', borderRadius: '10px', background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#d4af37" strokeWidth="1.5"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
                  </div>
                  <div style={{ flex: 1 }}><div style={{ fontWeight: 500, color: 'var(--text-primary, #fff)' }}>macOS App</div><div style={{ fontSize: '0.75rem', color: 'var(--text-secondary, #888)' }}>macOS 11+</div></div>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--text-secondary, #888)" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                </a>

                <a href="https://storage.googleapis.com/najdangpt-downloads/Sanctumly.ipa" download style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '0.875rem', background: 'var(--bg-primary, #0d0d1a)', borderRadius: '0.5rem', textDecoration: 'none', marginBottom: '0.75rem' }}>
                  <div style={{ width: '40px', height: '40px', borderRadius: '10px', background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="#d4af37"><path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.81-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11z"/></svg>
                  </div>
                  <div style={{ flex: 1 }}><div style={{ fontWeight: 500, color: 'var(--text-primary, #fff)' }}>iOS App (IPA)</div><div style={{ fontSize: '0.75rem', color: 'var(--text-secondary, #888)' }}>Requires sideloading</div></div>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--text-secondary, #888)" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                </a>

                <a href="https://storage.googleapis.com/najdangpt-downloads/Sanctumly.apk" download style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '0.875rem', background: 'var(--bg-primary, #0d0d1a)', borderRadius: '0.5rem', textDecoration: 'none', marginBottom: '0.75rem' }}>
                  <div style={{ width: '40px', height: '40px', borderRadius: '10px', background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="#d4af37"><path d="M17.6 9.48l1.84-3.18c.16-.31.04-.69-.26-.85-.29-.15-.65-.06-.83.22l-1.88 3.24a11.43 11.43 0 0 0-8.94 0L5.65 5.67c-.19-.28-.54-.37-.83-.22-.3.16-.42.54-.26.85l1.84 3.18C4.8 11.16 3.5 13.84 3.5 16.5h17c0-2.66-1.3-5.34-2.9-7.02zM7 14.5c-.55 0-1-.45-1-1s.45-1 1-1 1 .45 1 1-.45 1-1 1zm10 0c-.55 0-1-.45-1-1s.45-1 1-1 1 .45 1 1-.45 1-1 1z"/></svg>
                  </div>
                  <div style={{ flex: 1 }}><div style={{ fontWeight: 500, color: 'var(--text-primary, #fff)' }}>Android App (APK)</div><div style={{ fontSize: '0.75rem', color: 'var(--text-secondary, #888)' }}>Android 7.0+</div></div>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--text-secondary, #888)" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                </a>

                <p style={{ marginTop: '1rem', fontSize: '0.75rem', color: 'var(--text-secondary, #888)', textAlign: 'center' }}>
                  iOS requires sideloading via{' '}
                  <a href="https://altstore.io" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent-color, #8b5cf6)' }}>AltStore</a>
                  {' '}or{' '}
                  <a href="https://sideloadly.io" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent-color, #8b5cf6)' }}>Sideloadly</a>
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Voice Conversation Mode Overlay */}
        {voiceMode && (
          <div style={{ position: 'fixed', inset: 0, background: 'rgba(15, 15, 35, 0.98)', backdropFilter: 'blur(20px)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', zIndex: 2000, padding: '2rem' }}>
            <button onClick={stopVoiceMode} style={{ position: 'absolute', top: '1.5rem', right: '1.5rem', background: 'rgba(255, 255, 255, 0.1)', border: 'none', borderRadius: '50%', width: '48px', height: '48px', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}>
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>

            <div style={{ position: 'absolute', top: '1.5rem', left: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.5rem 1rem', background: 'rgba(255, 255, 255, 0.1)', borderRadius: '2rem', cursor: 'pointer' }} onClick={() => setTtsLanguage(prev => prev === 'en-US' ? 'sr-RS' : 'en-US')}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={ttsLanguage === 'sr-RS' ? '#ffd700' : 'white'} strokeWidth="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>
              <span style={{ color: ttsLanguage === 'sr-RS' ? '#ffd700' : 'white', fontWeight: 600 }}>{ttsLanguage === 'sr-RS' ? 'Serbian' : 'English'}</span>
            </div>

            <div style={{
              width: '200px', height: '200px', borderRadius: '50%',
              background: voiceState === 'listening' ? 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)' : voiceState === 'thinking' ? 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)' : voiceState === 'speaking' ? 'linear-gradient(135deg, #22c55e 0%, #16a34a 100%)' : 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: voiceState === 'listening' ? '0 0 60px rgba(239, 68, 68, 0.5)' : voiceState === 'thinking' ? '0 0 60px rgba(245, 158, 11, 0.5)' : voiceState === 'speaking' ? '0 0 60px rgba(34, 197, 94, 0.5)' : '0 0 60px rgba(102, 126, 234, 0.3)',
              animation: voiceState === 'listening' ? 'pulse 1.5s ease-in-out infinite' : voiceState === 'thinking' ? 'pulse 0.8s ease-in-out infinite' : voiceState === 'speaking' ? 'pulse 1s ease-in-out infinite' : 'none',
              transition: 'all 0.3s ease', cursor: voiceState === 'idle' ? 'pointer' : 'default'
            }}
            onMouseDown={voiceState === 'idle' ? startVoiceRecording : undefined}
            onMouseUp={voiceState === 'listening' ? stopVoiceRecording : undefined}
            onMouseLeave={voiceState === 'listening' ? stopVoiceRecording : undefined}
            onTouchStart={voiceState === 'idle' ? startVoiceRecording : undefined}
            onTouchEnd={voiceState === 'listening' ? stopVoiceRecording : undefined}
            >
              {voiceState === 'listening' ? (
                <svg width="80" height="80" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="1.5"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>
              ) : voiceState === 'thinking' ? (
                <svg width="80" height="80" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="1.5" style={{ animation: 'spin 2s linear infinite' }}><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
              ) : voiceState === 'speaking' ? (
                <svg width="80" height="80" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="1.5"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/></svg>
              ) : (
                <svg width="80" height="80" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="1.5"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>
              )}
            </div>

            <div style={{ marginTop: '2rem', fontSize: '1.5rem', fontWeight: 600, color: 'white', textAlign: 'center' }}>
              {voiceState === 'listening' ? 'Listening...' : voiceState === 'thinking' ? 'Thinking...' : voiceState === 'speaking' ? 'Speaking...' : 'Hold to speak'}
            </div>

            <div style={{ marginTop: '0.75rem', fontSize: '0.875rem', color: 'rgba(255, 255, 255, 0.6)', textAlign: 'center' }}>
              {voiceState === 'idle' ? 'Press and hold the circle to talk' : voiceState === 'listening' ? 'Release to send' : voiceState === 'thinking' ? 'Processing your message...' : 'Sanctumly is responding'}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
