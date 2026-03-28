import { useEffect, useRef } from 'react'

// ── TTS helpers ──────────────────────────────────────────────────────────────

let currentUtterance = null

function _getVoicesReady() {
  return new Promise((resolve) => {
    const voices = window.speechSynthesis.getVoices()
    if (voices.length > 0) { resolve(voices); return }
    window.speechSynthesis.onvoiceschanged = () => resolve(window.speechSynthesis.getVoices())
    setTimeout(() => resolve(window.speechSynthesis.getVoices()), 1000)
  })
}

function _pickVoice(voices, lang = 'en') {
  if (!voices || voices.length === 0) return null

  // Helper: is a voice female?
  const isFemale = (v) => {
    const n = v.name.toLowerCase()
    return (
      n.includes('female') ||
      n.includes('woman')  ||
      n.includes('zira')   ||
      n.includes('samantha') ||
      n.includes('karen')  ||
      n.includes('moira')  ||
      n.includes('victoria') ||
      n.includes('hazel')  ||
      n.includes('fiona')  ||
      n.includes('tessa')  ||
      n.includes('veena')  ||
      n.includes('neerja') ||
      n.includes('lekha')  ||
      n.includes('heera')  ||
      n.includes('kanya')  ||
      n.includes('allison') ||
      n.includes('ava')    ||
      n.includes('susan')  ||
      n.includes('kate')   ||
      n.includes('emily')  ||
      n.includes('aria')   ||
      n.includes('siri')
    )
  }

  // For Hindi — prefer female voice
  if (lang === 'hi' || lang === 'hi-IN') {
    return (
      voices.find(v => isFemale(v) && v.lang === 'hi-IN') ||
      voices.find(v => isFemale(v) && v.lang.startsWith('hi')) ||
      voices.find(v => v.lang === 'hi-IN') ||
      voices.find(v => v.lang.startsWith('hi')) ||
      null
    )
  }

  // For Marathi — prefer female voice
  if (lang === 'mr' || lang === 'mr-IN') {
    return (
      voices.find(v => isFemale(v) && v.lang === 'mr-IN') ||
      voices.find(v => isFemale(v) && v.lang.startsWith('mr')) ||
      voices.find(v => v.lang === 'mr-IN') ||
      voices.find(v => v.lang.startsWith('mr')) ||
      voices.find(v => isFemale(v) && v.lang.startsWith('hi')) ||
      null
    )
  }

  // For English — prioritise well-known female voices
  return (
    voices.find(v => v.name.includes('Zira')     && v.lang.startsWith('en')) ||
    voices.find(v => v.name.includes('Samantha') && v.lang.startsWith('en')) ||
    voices.find(v => v.name.includes('Karen')    && v.lang.startsWith('en')) ||
    voices.find(v => v.name.includes('Moira')    && v.lang.startsWith('en')) ||
    voices.find(v => v.name.includes('Veena')    && v.lang.startsWith('en')) ||
    voices.find(v => v.name.includes('Victoria') && v.lang.startsWith('en')) ||
    voices.find(v => v.name.includes('Hazel')    && v.lang.startsWith('en')) ||
    voices.find(v => v.name.includes('Fiona')    && v.lang.startsWith('en')) ||
    voices.find(v => v.name.includes('Tessa')    && v.lang.startsWith('en')) ||
    voices.find(v => isFemale(v)                 && v.lang === 'en-GB')      ||
    voices.find(v => isFemale(v)                 && v.lang.startsWith('en-IN')) ||
    voices.find(v => isFemale(v)                 && v.lang.startsWith('en')) ||
    voices.find(v => v.lang.startsWith('en'))
  )
}

export async function speakText(text, { rate = 0.90, pitch = 1.1, volume = 1, lang = 'en' } = {}) {
  if (!('speechSynthesis' in window)) return
  if (!text || text.trim() === '') return
  window.speechSynthesis.cancel()
  const voices = await _getVoicesReady()
  const utter = new SpeechSynthesisUtterance(text)
  utter.rate = rate; utter.pitch = pitch; utter.volume = volume
  const voice = _pickVoice(voices, lang)
  if (voice) { utter.voice = voice; utter.lang = voice.lang }
  utter.onerror = (e) => { if (e.error !== 'interrupted') console.warn('TTS error:', e.error) }
  currentUtterance = utter
  if (window.speechSynthesis.paused) window.speechSynthesis.resume()
  window.speechSynthesis.speak(utter)
  const keepAlive = setInterval(() => {
    if (!window.speechSynthesis.speaking) clearInterval(keepAlive)
    else { window.speechSynthesis.pause(); window.speechSynthesis.resume() }
  }, 10000)
  utter.onend = () => clearInterval(keepAlive)
}

export function stopSpeaking() {
  window.speechSynthesis?.cancel()
  currentUtterance = null
}

// ── Typing indicator ─────────────────────────────────────────────────────────

function TypingIndicator() {
  return (
    <div className="chat-bubble jarvis-bubble typing-bubble" id="typing-indicator">
      <div className="bubble-avatar">🤖</div>
      <div className="bubble-content">
        <span className="loading-dots">
          <span /><span /><span />
        </span>
      </div>
    </div>
  )
}

// ── MessageBubble ────────────────────────────────────────────────────────────

function MessageBubble({ msg, onSpeak }) {
  const isUser  = msg.role === 'user'
  const isError = msg.error

  const handleSpeak = () => onSpeak(msg.text, msg.lang || 'en')

  return (
    <div
      className={`chat-bubble ${isUser ? 'user-bubble' : 'jarvis-bubble'} ${isError ? 'error-bubble' : ''}`}
      id={`msg-${msg.id}`}
    >
      {/* JARVIS avatar (left) */}
      {!isUser && (
        <div className="bubble-avatar">🤖</div>
      )}

      <div className="bubble-body">
        {/* Sender label */}
        {!isUser && (
          <div className="bubble-sender">
            NEMO
            {msg.lang && msg.lang !== 'en' && (
              <span className={`lang-badge ${msg.lang}`}>{msg.lang.toUpperCase()}</span>
            )}
          </div>
        )}

        {/* Main text */}
        <div className="bubble-content">{msg.text}</div>

        {/* Intent / confidence tags */}
        {!isUser && msg.intent && (
          <div className="bubble-meta">
            <span className="meta-tag">🎯 {msg.intent.replace(/_/g, ' ').toUpperCase()}</span>
            {msg.confidence !== undefined && (
              <span className="meta-tag">⚡ {Math.round(msg.confidence * 100)}%</span>
            )}
            {Object.entries(msg.entities || {}).map(([k, v]) => (
              <span key={k} className="meta-tag">{k}: {String(v)}</span>
            ))}
          </div>
        )}

        {/* System output */}
        {msg.systemOutput && (
          <div className="bubble-system-output">{msg.systemOutput}</div>
        )}

        {/* Footer: timestamp + TTS */}
        <div className="bubble-footer">
          <span className="bubble-time">{msg.time}</span>
          {!isUser && (
            <button
              className="tts-btn"
              onClick={handleSpeak}
              title="Speak this response"
              aria-label="Play voice"
            >
              🔊
            </button>
          )}
        </div>
      </div>

      {/* User avatar (right) */}
      {isUser && (
        <div className="bubble-avatar user-avatar">👤</div>
      )}
    </div>
  )
}

// ── ChatWindow ───────────────────────────────────────────────────────────────

export default function ChatWindow({ messages, isTyping, isSpeaking, onSpeak, onStopSpeak }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isTyping])

  return (
    <div className="chat-window" id="chat-window">
      {messages.length === 0 && !isTyping ? (
        <div className="chat-empty">
          <div className="chat-empty-orb">🤖</div>
          <p className="chat-empty-title">Good evening. NEMO online.</p>
          <p className="chat-empty-sub">
            All systems nominal. Awaiting your command, Director.<br/>
            Speak or type to begin.
          </p>
        </div>
      ) : (
        <>
          {messages.map((msg) => (
            <MessageBubble key={msg.id} msg={msg} onSpeak={onSpeak} />
          ))}
          {isTyping && <TypingIndicator />}
        </>
      )}
      <div ref={bottomRef} />

      {/* Floating stop-speak button */}
      {isSpeaking && (
        <button
          id="stop-speaking-btn"
          className="stop-speaking-btn"
          onClick={onStopSpeak}
          title="Stop NEMO speaking"
        >
          🔇 Stop Speaking
        </button>
      )}
    </div>
  )
}
