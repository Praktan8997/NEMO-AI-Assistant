import { useState, useEffect, useCallback, useRef } from 'react'
import VoiceInput from './components/VoiceInput'
import AgentStatus from './components/AgentStatus'
import ChatWindow, { speakText, stopSpeaking } from './components/ChatWindow'
import CommandHistory from './components/CommandHistory'
import SystemStats from './components/SystemStats'

const API_BASE = '/api'
const HEALTH_POLL_MS = 4000
const SESSION_ID = `jarvis_ui_${Date.now()}`

let msgCounter = 0
const mkId = () => `msg_${++msgCounter}`

const now = () =>
  new Date().toLocaleTimeString('en-US', {
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
  })

// ── Language config ────────────────────────────────────────────────────────
const LANGUAGES = [
  { code: 'en', label: 'EN',  flag: '🇺🇸', voiceCode: 'en-US', ttsCode: 'en-IN',
    placeholder: 'Type a command — e.g. Open Chrome, Search for Python...' },
  { code: 'hi', label: 'हि',  flag: '🇮🇳', voiceCode: 'hi-IN', ttsCode: 'hi-IN',
    placeholder: 'आदेश दें — जैसे Chrome खोलो, Discord लॉन्च करो...' },
  { code: 'mr', label: 'मर', flag: '🇮🇳', voiceCode: 'mr-IN', ttsCode: 'mr-IN',
    placeholder: 'आदेश द्या — उदा. Chrome उघड, Discord सुरू कर...' },
]

export default function App() {
  const [messages,   setMessages]   = useState([])
  const [isTyping,   setIsTyping]   = useState(false)
  const [isSpeaking, setIsSpeaking] = useState(false)
  const [health,     setHealth]     = useState(null)
  const [history,    setHistory]    = useState([])
  const [backendOk,  setBackendOk]  = useState(null)
  const [convMode,   setConvMode]   = useState(null)
  const [clock,      setClock]      = useState('')
  const [lang,       setLang]       = useState(() => localStorage.getItem('jarvis_lang') || 'en')
  const healthTimer = useRef(null)

  const langConfig = LANGUAGES.find(l => l.code === lang) || LANGUAGES[0]

  // Persist language
  useEffect(() => { localStorage.setItem('jarvis_lang', lang) }, [lang])

  // Clock
  useEffect(() => {
    const tick = () => setClock(new Date().toLocaleTimeString('en-US', {
      hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
    }))
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [])

  // Health polling
  const fetchHealth = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/health/`)
      if (!res.ok) throw new Error()
      setHealth(await res.json())
      setBackendOk(true)
    } catch {
      setBackendOk(false)
    }
  }, [])

  const fetchHistory = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/health/history?limit=40`)
      if (!res.ok) return
      const data = await res.json()
      setHistory(data.items ?? [])
    } catch { /* silent */ }
  }, [])

  const fetchConvMode = useCallback(async () => {
    try {
      const res = await fetch('/')
      if (!res.ok) return
      const data = await res.json()
      setConvMode(data.conversation_mode === 'OpenRouter LLM' ? 'llm' : 'fallback')
    } catch { /* silent */ }
  }, [])

  useEffect(() => {
    fetchHealth(); fetchHistory(); fetchConvMode()
    healthTimer.current = setInterval(() => { fetchHealth(); fetchHistory() }, HEALTH_POLL_MS)
    return () => clearInterval(healthTimer.current)
  }, [fetchHealth, fetchHistory, fetchConvMode])

  // Pre-warm TTS voices
  useEffect(() => {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.getVoices()
      window.speechSynthesis.onvoiceschanged = () => {}
    }
  }, [])

  // TTS
  const handleSpeak = useCallback(async (text, ttsLang) => {
    setIsSpeaking(true)
    await speakText(text, { rate: 0.90, pitch: 1.1, lang: ttsLang || 'en' })
    const check = setInterval(() => {
      if (!window.speechSynthesis.speaking) { setIsSpeaking(false); clearInterval(check) }
    }, 300)
  }, [])

  const handleStopSpeak = useCallback(() => {
    stopSpeaking(); setIsSpeaking(false)
  }, [])

  // Command submission
  const handleCommand = useCallback(async (text, overrideLang) => {
    const activeLang = overrideLang || lang
    setMessages(prev => [...prev, { id: mkId(), role: 'user', text, time: now(), lang: activeLang }])
    setIsTyping(true)

    try {
      const res = await fetch(`${API_BASE}/commands/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, session_id: SESSION_ID, source: 'text', language: activeLang }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail ?? `HTTP ${res.status}`)
      }
      const data = await res.json()
      const responseLang = data.language || activeLang
      const responseTtsCode = LANGUAGES.find(l => l.code === responseLang)?.ttsCode || 'en-IN'
      setMessages(prev => [...prev, {
        id: mkId(), role: 'jarvis',
        text: data.response_text, time: now(),
        intent: data.nlp_result?.intent,
        confidence: data.nlp_result?.confidence,
        entities: data.nlp_result?.entities,
        systemOutput: data.automation_result?.output,
        error: data.automation_result?.success === false,
        lang: responseLang,
      }])
      handleSpeak(data.response_text, responseTtsCode)
      setTimeout(() => { fetchHealth(); fetchHistory() }, 600)
    } catch (e) {
      setMessages(prev => [...prev, {
        id: mkId(), role: 'jarvis',
        text: `I'm unable to reach my backend systems right now. ${e.message}.`,
        time: now(), error: true, lang: 'en',
      }])
    } finally {
      setIsTyping(false)
    }
  }, [lang, fetchHealth, fetchHistory, handleSpeak])

  // Clear session
  const clearSession = useCallback(async () => {
    setMessages([])
    stopSpeaking(); setIsSpeaking(false)
    try { await fetch(`${API_BASE}/commands/session/${SESSION_ID}`, { method: 'DELETE' }) } catch { /* silent */ }
  }, [])

  // Derived state
  const statusLabel = backendOk === null ? 'CONNECTING' : backendOk ? 'ONLINE' : 'OFFLINE'
  const statusCls   = backendOk === null ? 'loading'    : backendOk ? ''       : 'offline'

  // Quick commands per language
  const QUICK_CMDS = {
    en: ['Hello NEMO, how are you?', 'Open Chrome', 'Show system stats',
         'Search for latest AI news', 'Calculate 144 / 12', 'Open Notepad'],
    hi: ['Chrome खोलो', 'Discord लॉन्च करो', 'System stats बताओ',
         'Python tutorial सर्च करो', 'नमस्ते NEMO', 'Calculator खोलो'],
    mr: ['Chrome उघड', 'Discord सुरू कर', 'System माहिती सांग',
         'Python tutorial शोध', 'नमस्कार NEMO', 'Notepad उघड'],
  }
  const quickCmds = QUICK_CMDS[lang] || QUICK_CMDS.en

  return (
    <div className="app-layout">
      {/* Background glow blobs */}
      <div id="glow-blob-2" />
      <div id="scanlines" />

      {/* ─── HEADER ─────────────────────────────── */}
      <header className="app-header">
        <div className="header-logo">
          <div className="logo-icon">
            <div className="logo-inner">🤖</div>
          </div>
          <div className="logo-text">
            <h1>NEMO</h1>
            <span>Multi-Agent AI Assistant</span>
          </div>
        </div>

        <div className="header-controls">
          {/* Language Selector */}
          <div className="lang-selector" role="group" aria-label="Language">
            {LANGUAGES.map(l => (
              <button
                key={l.code}
                id={`lang-btn-${l.code}`}
                className={`lang-btn ${lang === l.code ? 'active' : ''}`}
                onClick={() => setLang(l.code)}
                title={`Switch to ${l.label}`}
              >
                {l.flag} {l.label}
              </button>
            ))}
          </div>

          {convMode && (
            <span className={`conv-mode-badge ${convMode}`}>
              {convMode === 'llm' ? '🧠 LLM' : '⚡ Fallback'}
            </span>
          )}

          <div className={`header-status ${statusCls}`}>
            <span className={`status-dot ${statusCls}`} />
            {statusLabel}
          </div>
        </div>

        <div className="header-time">{clock}</div>
      </header>

      {/* ─── SIDEBAR ────────────────────────────── */}
      <aside className="app-sidebar">
        <div className="sidebar-section-title">Agent Network</div>
        <div className="glass-card">
          <div className="scan-line" />
          <div className="card-header">
            <span className="card-icon">🤖</span>
            <span className="card-title">Agents</span>
          </div>
          <div className="card-body" style={{ padding: '12px 14px' }}>
            <AgentStatus agents={health?.agents ?? []} />
          </div>
        </div>

        <div className="sidebar-section-title">System Metrics</div>
        <div className="glass-card">
          <div className="scan-line" />
          <div className="card-header">
            <span className="card-icon">📊</span>
            <span className="card-title">Stats</span>
          </div>
          <div className="card-body">
            <SystemStats health={health} />
          </div>
        </div>
      </aside>

      {/* ─── MAIN CONTENT ───────────────────────── */}
      <main className="app-main">
        {/* Command Center */}
        <div className="glass-card">
          <div className="scan-line" />
          <div className="card-header">
            <span className="card-icon">⚡</span>
            <span className="card-title">Command Center</span>
            <span style={{
              marginLeft: 'auto',
              fontSize: '0.65rem',
              color: 'var(--accent-cyan)',
              fontFamily: 'var(--font-display)',
              opacity: 0.75,
            }}>
              {langConfig.flag} {langConfig.label}
            </span>
          </div>
          <div className="card-body">
            <VoiceInput
              onSubmit={handleCommand}
              isLoading={isTyping}
              lang={lang}
              voiceCode={langConfig.voiceCode}
              placeholder={langConfig.placeholder}
            />
          </div>
        </div>

        {/* Chat Window */}
        <div className="glass-card" style={{ flex: 1 }}>
          <div className="scan-line" />
          <div className="card-header">
            <span className="card-icon">💬</span>
            <span className="card-title">Conversation</span>
            <span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{
                fontSize: '0.62rem',
                color: 'var(--text-muted)',
                fontFamily: 'var(--font-hud)',
              }}>
                {messages.length} msg{messages.length !== 1 ? 's' : ''}
              </span>
              {messages.length > 0 && (
                <button
                  id="clear-chat-btn"
                  className="clear-chat-btn"
                  onClick={clearSession}
                  title="Reset conversation"
                >
                  🗑 Clear
                </button>
              )}
            </span>
          </div>
          <div className="card-body">
            <ChatWindow
              messages={messages}
              isTyping={isTyping}
              isSpeaking={isSpeaking}
              onSpeak={handleSpeak}
              onStopSpeak={handleStopSpeak}
            />
          </div>
        </div>
      </main>

      {/* ─── RIGHT PANEL ────────────────────────── */}
      <aside className="app-panel">
        <div className="sidebar-section-title">Command Log</div>
        <div className="glass-card" style={{ flex: 1 }}>
          <div className="scan-line" />
          <div className="card-header">
            <span className="card-icon">🕒</span>
            <span className="card-title">History</span>
            <span style={{
              marginLeft: 'auto',
              fontSize: '0.6rem',
              color: 'var(--text-muted)',
              fontFamily: 'var(--font-hud)',
              background: 'rgba(0,212,255,0.08)',
              padding: '2px 7px',
              borderRadius: 8,
              border: '1px solid var(--border-dim)',
            }}>
              {history.length}
            </span>
          </div>
          <div className="card-body" style={{ padding: '12px 14px' }}>
            <CommandHistory
              history={history}
              onSelect={(item) => handleCommand(item.user_input)}
            />
          </div>
        </div>

        <div className="sidebar-section-title">Quick Actions</div>
        <div className="glass-card">
          <div className="scan-line" />
          <div className="card-header">
            <span className="card-icon">🚀</span>
            <span className="card-title">Shortcuts</span>
          </div>
          <div className="card-body" style={{
            padding: '12px 14px',
            display: 'flex',
            flexDirection: 'column',
            gap: 7,
          }}>
            {quickCmds.map(cmd => (
              <button
                key={cmd}
                className="quick-cmd-chip"
                style={{ width: '100%', textAlign: 'left', borderRadius: 'var(--radius-sm)' }}
                onClick={() => handleCommand(cmd)}
                disabled={isTyping}
              >
                {cmd}
              </button>
            ))}
          </div>
        </div>

        <div style={{ textAlign: 'center', marginTop: 'auto', paddingTop: 8 }}>
          <a
            href="http://localhost:8000/docs"
            target="_blank"
            rel="noopener noreferrer"
            className="api-docs-link"
          >
            📋 API DOCS ↗
          </a>
        </div>
      </aside>
    </div>
  )
}
