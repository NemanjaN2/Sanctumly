import { useState, useEffect, useRef, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { sendMessage, streamMessage, clearChat, submitFeedback, getConversations, getChatHistory } from '../api/chat'
import { uploadDocument } from '../api/upload'
import { marked } from 'marked'

export default function ChatPage({ user, onLogout }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [personality, setPersonality] = useState('default')
  const [sessionId, setSessionId] = useState(() => {
    const stored = localStorage.getItem('session_id')
    if (stored) return stored
    const newId = `session_${Date.now()}`
    localStorage.setItem('session_id', newId)
    return newId
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
  const [pendingImage, setPendingImage] = useState(null)
  const [conversations, setConversations] = useState([])
  const [loadingConversations, setLoadingConversations] = useState(false)
  const [activeConversationId, setActiveConversationId] = useState(null)
  const [hoveredMsg, setHoveredMsg] = useState(null)

  const messagesEndRef = useRef(null)
  const fileInputRef = useRef(null)
  const imageInputRef = useRef(null)
  const currentAudioRef = useRef(null)
  const textareaRef = useRef(null)

  const personalities = [
    { value: 'default', label: 'Default', icon: '◆' },
    { value: 'therapist', label: 'Wellness', icon: '♡' },
    { value: 'content', label: 'Content', icon: '✎' },
  ]
  if (user.is_creator) personalities.push({ value: 'hacker', label: 'Security', icon: '⌘' })

  const suggestions = [
    { label: 'Brainstorm', sub: 'ideas for a project', prompt: 'Help me brainstorm creative ideas for my project' },
    { label: 'Explain', sub: 'a complex concept', prompt: 'Explain quantum computing in simple terms' },
    { label: 'Analyze', sub: 'uploaded document', prompt: 'Analyze the document I uploaded and summarize key points' },
    { label: 'Write', sub: 'some code', prompt: 'Write a Python script to process CSV files' },
  ]

  const currentPersonality = personalities.find(p => p.value === personality)

  const fetchConversations = useCallback(async () => {
    if (!user?.username) return
    setLoadingConversations(true)
    try { setConversations(await getConversations(user.username)) } catch {}
    finally { setLoadingConversations(false) }
  }, [user?.username])

  useEffect(() => { fetchConversations() }, [fetchConversations])

  const loadConversation = async (sid) => {
    try {
      setLoading(true)
      const h = await getChatHistory(sid)
      setMessages(h.map(m => ({ role: m.role, content: m.content, timestamp: m.timestamp })))
      setSessionId(sid); localStorage.setItem('session_id', sid)
      setActiveConversationId(sid); setSidebarOpen(false)
    } catch { setError('Failed to load conversation') }
    finally { setLoading(false) }
  }

  const handleNewChat = () => {
    const s = `session_${Date.now()}`
    setSessionId(s); localStorage.setItem('session_id', s)
    setMessages([]); setActiveConversationId(null); setUploadedFiles([]); setMessageFeedback({}); setSidebarOpen(false)
  }

  const fmtDate = (ts) => {
    if (!ts) return ''
    const d = Date.now() - new Date(ts).getTime()
    const m = Math.floor(d/60000)
    if (m < 1) return 'now'
    if (m < 60) return `${m}m`
    const h = Math.floor(d/3600000)
    if (h < 24) return `${h}h`
    const dy = Math.floor(d/86400000)
    if (dy < 7) return `${dy}d`
    return new Date(ts).toLocaleDateString('en', { month: 'short', day: 'numeric' })
  }

  const trunc = (t, n=34) => {
    if (!t) return 'New conversation'
    const c = t.replace(/[#*_`~\[\]()]/g,'').trim()
    return c.length <= n ? c : c.slice(0,n).trim()+'…'
  }

  useEffect(() => { document.body.classList.toggle('no-scroll', sidebarOpen); return () => document.body.classList.remove('no-scroll') }, [sidebarOpen])
  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])
  useEffect(() => { if (error) { const t=setTimeout(()=>setError(''),5000); return ()=>clearTimeout(t) } }, [error])
  useEffect(() => { if (success) { const t=setTimeout(()=>setSuccess(''),3000); return ()=>clearTimeout(t) } }, [success])
  useEffect(() => { if (textareaRef.current) { textareaRef.current.style.height='auto'; textareaRef.current.style.height=Math.min(textareaRef.current.scrollHeight,200)+'px' } }, [input])

  const handleImageSelect = (e) => {
    const f = e.target.files[0]; if (!f) return
    if (!f.type.startsWith('image/')) { setError('Select an image file'); return }
    if (f.size > 4*1024*1024) { setError('Image too large (4MB max)'); return }
    const p = URL.createObjectURL(f)
    const r = new FileReader()
    r.onload = (ev) => setPendingImage({ file:f, preview:p, base64:ev.target.result.split(',')[1] })
    r.readAsDataURL(f)
    if (imageInputRef.current) imageInputRef.current.value=''
  }
  const removePendingImage = () => { if (pendingImage?.preview) URL.revokeObjectURL(pendingImage.preview); setPendingImage(null) }

  // ══════════════════════════════
  // SEND — streams text replies, falls back to non-streaming for images
  // ══════════════════════════════
  const handleSend = async (text=null) => {
    const t = text||input; if ((!t.trim()&&!pendingImage)||loading) return
    const display = pendingImage ? `📷 ${t||'Analyze this image'}` : t
    const actual = t.trim()||(pendingImage?'What do you see in this image? Describe and analyze it.':'')
    const img64 = pendingImage?.base64||null
    setMessages(p=>[...p,{role:'user',content:display,timestamp:new Date().toISOString(),imagePreview:pendingImage?.preview||null}])
    setInput(''); removePendingImage(); setLoading(true); setError('')

    // Images can't stream (vision endpoint) — use the normal path
    if (img64) {
      try {
        const r = await sendMessage(actual,sessionId,user.username,personality,img64)
        setMessages(p=>[...p,{role:'assistant',content:r.response,timestamp:new Date().toISOString()}])
        fetchConversations()
      } catch { setError('Failed to send'); setMessages(p=>[...p,{role:'assistant',content:'Sorry, something went wrong.',timestamp:new Date().toISOString()}]) }
      finally { setLoading(false) }
      return
    }

    // Streaming path: add an empty assistant message, then fill it as tokens arrive
    const assistantTs = new Date().toISOString()
    setMessages(p=>[...p,{role:'assistant',content:'',timestamp:assistantTs,streaming:true}])
    try {
      await streamMessage(actual, sessionId, user.username, personality, (token) => {
        setMessages(p => {
          const next = [...p]
          for (let i = next.length - 1; i >= 0; i--) {
            if (next[i].role === 'assistant' && next[i].streaming) {
              next[i] = { ...next[i], content: next[i].content + token }
              break
            }
          }
          return next
        })
      })
      setMessages(p => p.map(m => m.streaming ? { ...m, streaming:false } : m))
      fetchConversations()
    } catch (e) {
      setMessages(p => {
        const next = p.filter(m => !(m.role==='assistant' && m.streaming && !m.content))
        return next.map(m => m.streaming ? { ...m, streaming:false } : m)
      })
      setError(e.message || 'Failed to send')
    } finally {
      setLoading(false)
    }
  }

  const handleClearChat = async () => {
    if (!confirm('Clear all messages?')) return
    try { await clearChat(sessionId); setMessages([]); fetchConversations() } catch { setError('Failed to clear') }
  }

  const handleFileUpload = async (e) => {
    const f=e.target.files[0]; if (!f) return
    if (f.size>20*1024*1024) { setError('File too large (20MB max)'); return }
    setUploading(true); setUploadProgress(0)
    const iv=setInterval(()=>setUploadProgress(p=>p>=90?(clearInterval(iv),90):p+10),200)
    try { const r=await uploadDocument(f,sessionId); clearInterval(iv); setUploadProgress(100); setUploadedFiles(p=>[...p,r.filename]); setTimeout(()=>setUploadProgress(0),1000) }
    catch { clearInterval(iv); setError('Upload failed'); setUploadProgress(0) }
    finally { setUploading(false); if(fileInputRef.current) fileInputRef.current.value='' }
  }

  const handleKeyDown = (e) => { if (e.key==='Enter'&&!e.shiftKey) { e.preventDefault(); handleSend() } }

  const handleFeedback = async (i,type) => { setMessageFeedback(p=>({...p,[i]:type})); try{await submitFeedback(messages[i].content,type,sessionId,user.username)}catch{} }
  const handleCopy = (c) => { navigator.clipboard.writeText(c); setSuccess('Copied') }

  const handleReadAloud = async (i,c) => {
    if (currentAudioRef.current) { currentAudioRef.current.pause(); currentAudioRef.current=null }
    if (speakingMessageIndex===i) { setSpeakingMessageIndex(null); return }
    setSpeakingMessageIndex(i)
    try {
      const r = await fetch(`${import.meta.env.VITE_API_URL||'https://sanctumly-production.up.railway.app'}/speech/tts`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:c,language:ttsLanguage,voice_gender:'female'})})
      if (!r.ok) throw 0
      const d=await r.json()
      const b=new Blob([Uint8Array.from(atob(d.audio),c=>c.charCodeAt(0))],{type:'audio/mp3'})
      const u=URL.createObjectURL(b), a=new Audio(u)
      currentAudioRef.current=a
      a.onended=()=>{setSpeakingMessageIndex(null);URL.revokeObjectURL(u);currentAudioRef.current=null}
      a.onerror=()=>{setSpeakingMessageIndex(null);currentAudioRef.current=null}
      a.play()
    } catch { setSpeakingMessageIndex(null) }
  }

  useEffect(()=>{return()=>{if(currentAudioRef.current){currentAudioRef.current.pause();currentAudioRef.current=null}}},[])

  useEffect(()=>{
    const h=(e)=>{e.preventDefault();setDeferredPrompt(e);setShowInstallPrompt(true)}
    window.addEventListener('beforeinstallprompt',h); window.addEventListener('appinstalled',()=>setShowInstallPrompt(false))
    return()=>window.removeEventListener('beforeinstallprompt',h)
  },[])

  const handleVoiceClick = async () => {
    if (isRecording) { mediaRecorder?.stop(); return }
    try {
      const s=await navigator.mediaDevices.getUserMedia({audio:true})
      const rec=new MediaRecorder(s,{mimeType:'audio/webm'}), chunks=[]
      rec.ondataavailable=(e)=>chunks.push(e.data)
      rec.onstop=async()=>{s.getTracks().forEach(t=>t.stop());await transcribeAudio(new Blob(chunks,{type:'audio/webm'}))}
      rec.start(); setMediaRecorder(rec); setIsRecording(true)
    } catch { setError('Microphone denied') }
  }

  const transcribeAudio = async (b) => {
    try { setLoading(true); const fd=new FormData(); fd.append('file',b,'audio.webm')
      const r=await fetch(`${import.meta.env.VITE_API_URL||'https://sanctumly-production.up.railway.app'}/speech/transcribe`,{method:'POST',body:fd})
      if(!r.ok) throw 0; const d=await r.json()
      if(d.success&&d.transcript) setInput(d.transcript); else setError('No speech detected')
    } catch { setError('Transcription failed') }
    finally { setLoading(false); setIsRecording(false); setMediaRecorder(null) }
  }

  const startVoiceMode=()=>{setVoiceMode(true);setVoiceState('idle')}
  const stopVoiceMode=()=>{setVoiceMode(false);setVoiceState('idle');mediaRecorder?.stop();if(currentAudioRef.current){currentAudioRef.current.pause();currentAudioRef.current=null};setSpeakingMessageIndex(null)}

  const startVoiceRecording = async () => {
    if(!voiceMode) return; setVoiceState('listening')
    try {
      const s=await navigator.mediaDevices.getUserMedia({audio:true})
      let m='audio/webm'; if(MediaRecorder.isTypeSupported('audio/webm;codecs=opus'))m='audio/webm;codecs=opus'; else if(MediaRecorder.isTypeSupported('audio/mp4'))m='audio/mp4'
      const rec=new MediaRecorder(s,{mimeType:m}),chunks=[]
      rec.ondataavailable=(e)=>{if(e.data.size>0)chunks.push(e.data)}
      rec.onstop=async()=>{s.getTracks().forEach(t=>t.stop());if(!chunks.length){setVoiceState('idle');return};const b=new Blob(chunks,{type:m});if(b.size<1000){setError('Too short');setVoiceState('idle');return};await processVoiceInput(b)}
      rec.start(250); setMediaRecorder(rec)
    } catch { setError('Mic denied'); setVoiceState('idle') }
  }
  const stopVoiceRecording=()=>{if(mediaRecorder?.state==='recording'){mediaRecorder.stop();setMediaRecorder(null)}}

  const processVoiceInput = async (b) => {
    try { setVoiceState('thinking')
      const fd=new FormData(); fd.append('file',b,`audio.${b.type.includes('mp4')?'mp4':'webm'}`)
      const tr=await fetch(`${import.meta.env.VITE_API_URL||'https://sanctumly-production.up.railway.app'}/speech/transcribe`,{method:'POST',body:fd})
      if(!tr.ok) throw 0; const td=await tr.json()
      if(!td.success||!td.transcript){setError('No speech');setVoiceState('idle');return}
      setMessages(p=>[...p,{role:'user',content:td.transcript,timestamp:new Date().toISOString()}])
      const cr=await sendMessage(td.transcript,sessionId,user.username,personality)
      setMessages(p=>[...p,{role:'assistant',content:cr.response,timestamp:new Date().toISOString()}])
      setVoiceState('speaking'); await speakResponse(cr.response)
    } catch { setError('Voice failed'); setVoiceState('idle') }
  }

  const speakResponse = async (t) => {
    try {
      const r=await fetch(`${import.meta.env.VITE_API_URL||'https://sanctumly-production.up.railway.app'}/speech/tts`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:t,language:ttsLanguage,voice_gender:'female'})})
      if(!r.ok) throw 0; const d=await r.json()
      const b=new Blob([Uint8Array.from(atob(d.audio),c=>c.charCodeAt(0))],{type:'audio/mp3'})
      const u=URL.createObjectURL(b),a=new Audio(u); currentAudioRef.current=a
      a.onended=()=>{URL.revokeObjectURL(u);currentAudioRef.current=null;if(voiceMode)setVoiceState('idle')}
      a.onerror=()=>setVoiceState('idle'); await a.play()
    } catch { setVoiceState('idle') }
  }

  useEffect(()=>{
    const h=(e)=>{const items=e.clipboardData?.items;if(!items)return;for(const i of items){if(i.type.startsWith('image/')){e.preventDefault();const f=i.getAsFile();if(f){const p=URL.createObjectURL(f),r=new FileReader();r.onload=(ev)=>setPendingImage({file:f,preview:p,base64:ev.target.result.split(',')[1]});r.readAsDataURL(f)}break}}}
    window.addEventListener('paste',h); return()=>window.removeEventListener('paste',h)
  },[])

  // ══════════════════════════════
  // RENDER
  // ══════════════════════════════

  return (
    <div className="app-shell">
      {sidebarOpen && <div className="overlay" onClick={() => setSidebarOpen(false)} />}

      {/* ── Sidebar ── */}
      <aside className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
        <div className="sb-head">
          <span className="sb-brand">Sanctumly</span>
          <button className="sb-close" onClick={() => setSidebarOpen(false)}>✕</button>
        </div>
        <div className="sb-scroll">
          <div className="sb-user-card">
            <div className="sb-avatar">{user.username?.[0]?.toUpperCase()}</div>
            <div>
              <div className="sb-username">{user.username}</div>
              {user.is_creator && <div className="sb-creator-tag">Creator</div>}
            </div>
          </div>

          <div className="sb-group">
            <div className="sb-group-label">Agent</div>
            {personalities.map(p => (
              <button key={p.value} className={`sb-agent ${personality===p.value?'active':''}`}
                onClick={() => { setPersonality(p.value); setSidebarOpen(false) }}>
                <span className="sb-agent-icon">{p.icon}</span>
                <span>{p.label}</span>
                {personality===p.value && <span className="sb-agent-check">✓</span>}
              </button>
            ))}
          </div>

          <div className="sb-group">
            <div className="sb-group-header">
              <span className="sb-group-label">History</span>
              <button className="sb-new" onClick={handleNewChat}>+ New</button>
            </div>
            <div className="sb-convos">
              {loadingConversations ? <div className="sb-muted">Loading…</div> :
               conversations.length===0 ? <div className="sb-muted">No conversations</div> :
               conversations.map(c => (
                <button key={c.session_id} className={`sb-convo ${sessionId===c.session_id?'active':''}`}
                  onClick={() => loadConversation(c.session_id)}>
                  <span className="sb-convo-t">{trunc(c.title)}</span>
                  <span className="sb-convo-d">{fmtDate(c.last_message_at)}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="sb-group sb-bottom-links">
            {user.is_admin && <Link to="/admin" className="sb-link">Admin Panel</Link>}
            <Link to="/wellness" className="sb-link">My Wellness</Link>
            <button className="sb-link" onClick={handleClearChat}>Clear Chat</button>
            <button className="sb-link" onClick={() => setShowDownloadModal(true)}>Download Apps</button>
            <button className="sb-link danger" onClick={onLogout}>Log out</button>
          </div>
        </div>
      </aside>

      {/* ── Main ── */}
      <main className="main-col">
        <header className="top-bar">
          <div className="top-left">
            <button className="menu-btn" onClick={() => setSidebarOpen(true)}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
            </button>
            <span className="top-title">Sanctumly</span>
            <span className="top-mode">{currentPersonality?.label}</span>
          </div>
          <div className="top-right">
            <button className="top-pill" onClick={() => setTtsLanguage(p => p==='en-US'?'sr-RS':'en-US')}>
              <span className={ttsLanguage==='sr-RS'?'gold':''}>{ttsLanguage==='sr-RS'?'SR':'EN'}</span>
            </button>
            <button className="top-pill voice" onClick={startVoiceMode}>Voice</button>
          </div>
        </header>

        <div className="chat-area">
          <div className="chat-inner">
            {error && <div className="notif error">{error}</div>}
            {success && <div className="notif ok">{success}</div>}

            {messages.length === 0 ? (
              <div className="empty">
                <img src="/logo.png" alt="" className="empty-logo" />
                <h2 className="empty-h">Sanctumly</h2>
                <p className="empty-p">What can I help you with?</p>
                <div className="suggestion-row">
                  {suggestions.map((s,i) => (
                    <button key={i} className="suggestion" onClick={() => handleSend(s.prompt)}>
                      <span className="suggestion-label">{s.label}</span>
                      <span className="suggestion-sub">{s.sub}</span>
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="msg-stack">
                {messages.map((m,i) => (
                  <div key={i} className={`msg ${m.role}`}
                    onMouseEnter={() => m.role==='assistant' && setHoveredMsg(i)}
                    onMouseLeave={() => setHoveredMsg(null)}>
                    {m.imagePreview && <img src={m.imagePreview} alt="" className="msg-preview" />}
                    {m.role === 'assistant' ? (
                      <div className="md" dangerouslySetInnerHTML={{ __html: marked(m.content || '') }} />
                    ) : (
                      <div className="msg-body">{m.content}</div>
                    )}
                    {m.role==='assistant' && hoveredMsg===i && !m.streaming && (
                      <div className="msg-toolbar">
                        <button onClick={() => handleCopy(m.content)}>Copy</button>
                        <button className={speakingMessageIndex===i?'active':''} onClick={() => handleReadAloud(i,m.content)}>
                          {speakingMessageIndex===i?'Stop':'Read'}
                        </button>
                      </div>
                    )}
                  </div>
                ))}
                {loading && !messages.some(m => m.role==='assistant' && m.streaming && m.content) && (
                  <div className="msg assistant">
                    <div className="thinking"><span>Thinking</span><span className="dots"><i/><i/><i/></span></div>
                  </div>
                )}
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        </div>

        <div className="input-dock">
          <div className="input-dock-inner">
            {uploading && uploadProgress>0 && <div className="prog"><div className="prog-bar" style={{width:`${uploadProgress}%`}} /></div>}
            {pendingImage && (
              <div className="img-preview">
                <img src={pendingImage.preview} alt="" />
                <div className="img-preview-text"><strong>Image attached</strong><span>Sent with your message</span></div>
                <button className="img-preview-x" onClick={removePendingImage}>✕</button>
              </div>
            )}
            {uploadedFiles.length>0 && <div className="file-count">{uploadedFiles.length} file{uploadedFiles.length>1?'s':''} uploaded</div>}
            <div className="input-bar">
              <input type="file" ref={fileInputRef} onChange={handleFileUpload} accept=".txt,.pdf,.docx,.xlsx,.xls,.csv,.epub" hidden />
              <input type="file" ref={imageInputRef} onChange={handleImageSelect} accept="image/*" hidden />
              <button className="ib-icon" onClick={() => fileInputRef.current?.click()} disabled={uploading} title="File">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>
              </button>
              <button className="ib-icon" onClick={() => imageInputRef.current?.click()} disabled={loading} title="Image">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
              </button>
              <textarea ref={textareaRef} className="ib-text" value={input} onChange={e => setInput(e.target.value)}
                onKeyDown={handleKeyDown} placeholder={pendingImage?'Describe what to analyze…':'Message…'}
                disabled={loading} rows="1" />
              {(input.trim()||pendingImage) ? (
                <button className="ib-send" onClick={() => handleSend()} disabled={loading}>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
                </button>
              ) : (
                <button className={`ib-icon ${isRecording?'rec':''}`} onClick={handleVoiceClick} disabled={loading} title="Voice">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>
                </button>
              )}
            </div>
            <div className="fine-print">Sanctumly can make mistakes and cannot replace a real therapist.</div>
          </div>
        </div>
      </main>

      {/* Voice overlay */}
      {voiceMode && (
        <div className="voice-full">
          <div className="voice-bar">
            <button className="voice-lang" onClick={() => setTtsLanguage(p=>p==='en-US'?'sr-RS':'en-US')}>
              <span className={ttsLanguage==='sr-RS'?'gold':''}>{ttsLanguage==='sr-RS'?'Serbian':'English'}</span>
            </button>
            <button className="voice-x" onClick={stopVoiceMode}>✕</button>
          </div>
          <div className="voice-mid">
            <div className={`voice-orb ${voiceState}`}
              onMouseDown={voiceState==='idle'?startVoiceRecording:undefined}
              onMouseUp={voiceState==='listening'?stopVoiceRecording:undefined}
              onMouseLeave={voiceState==='listening'?stopVoiceRecording:undefined}
              onTouchStart={voiceState==='idle'?startVoiceRecording:undefined}
              onTouchEnd={voiceState==='listening'?stopVoiceRecording:undefined}>
              <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="1.5">
                {voiceState==='speaking'?<><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/></>:
                 voiceState==='thinking'?<><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></>:
                 <><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></>}
              </svg>
            </div>
            <div className="voice-state">{voiceState==='listening'?'Listening…':voiceState==='thinking'?'Thinking…':voiceState==='speaking'?'Speaking…':'Hold to speak'}</div>
            <div className="voice-hint">{voiceState==='idle'?'Press and hold':voiceState==='listening'?'Release to send':''}</div>
          </div>
          <div className="fine-print abs-bottom">Sanctumly can make mistakes and cannot replace a real therapist.</div>
        </div>
      )}

      {/* Download modal */}
      {showDownloadModal && (
        <div className="modal-bg" onClick={() => setShowDownloadModal(false)}>
          <div className="modal-box" onClick={e=>e.stopPropagation()}>
            <div className="modal-top"><span>Download Apps</span><button onClick={() => setShowDownloadModal(false)}>✕</button></div>
            <div className="modal-content">
              {[{l:'Windows',s:'Win 10/11',h:'https://github.com/NemanjaN2/Sanctumly/releases/download/Sanctumly/Sanctumly-Win10.zip'},
                {l:'macOS',s:'macOS 11+',h:'https://github.com/NemanjaN2/Sanctumly/releases/download/Sanctumly/Sanctumly.app.zip'},
                {l:'iOS (IPA)',s:'Sideload required',h:'https://github.com/NemanjaN2/Sanctumly/releases/download/Sanctumly/Sanctumly.ipa'},
                {l:'Android',s:'Android 7.0+',h:'https://github.com/NemanjaN2/Sanctumly/releases/download/Sanctumly/Sanctumly.apk'}
              ].map((a,i)=>(
                <a key={i} href={a.h} download className="dl-item">
                  <div><div className="dl-name">{a.l}</div><div className="dl-sub">{a.s}</div></div>
                  <span className="dl-arrow">↓</span>
                </a>
              ))}
              <p className="dl-note">iOS requires <a href="https://altstore.io" target="_blank" rel="noopener noreferrer">AltStore</a> or <a href="https://sideloadly.io" target="_blank" rel="noopener noreferrer">Sideloadly</a></p>
            </div>
          </div>
        </div>
      )}

      {showInstallPrompt && (
        <div className="pwa-bar">
          <span>Install Sanctumly for faster access</span>
          <button className="pwa-go" onClick={() => { deferredPrompt?.prompt(); setDeferredPrompt(null); setShowInstallPrompt(false) }}>Install</button>
          <button className="pwa-x" onClick={() => setShowInstallPrompt(false)}>✕</button>
        </div>
      )}
    </div>
  )
}
