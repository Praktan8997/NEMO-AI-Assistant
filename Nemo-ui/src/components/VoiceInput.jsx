import { useState, useRef, useEffect, useCallback } from 'react'

export default function VoiceInput({ onSubmit, isLoading, lang = 'en', voiceCode = 'en-US', placeholder }) {
  const [text, setText] = useState('')
  const [listening, setListening] = useState(false)
  const [autoFiring, setAutoFiring] = useState(false)
  const recognitionRef = useRef(null)
  const autoFireTimer  = useRef(null)

  // Stop recognition when language changes
  useEffect(() => {
    if (recognitionRef.current) {
      recognitionRef.current.stop()
      setListening(false)
    }
  }, [voiceCode])

  // Cleanup on unmount
  useEffect(() => () => clearTimeout(autoFireTimer.current), [])

  const handleSubmit = useCallback((overrideText) => {
    const trimmed = (overrideText ?? text).trim()
    if (!trimmed || isLoading) return
    onSubmit(trimmed)
    setText('')
    setAutoFiring(false)
  }, [text, isLoading, onSubmit])

  const handleKey = (e) => {
    if (e.key === 'Enter') handleSubmit()
  }

  const toggleVoice = () => {
    if (!('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
      alert('Voice recognition is not supported in this browser. Please use Chrome.')
      return
    }

    if (listening) {
      recognitionRef.current?.stop()
      setListening(false)
      clearTimeout(autoFireTimer.current)
      setAutoFiring(false)
      return
    }

    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    const recognition = new SR()
    recognition.lang            = voiceCode
    recognition.interimResults  = false
    recognition.maxAlternatives = 1

    recognition.onresult = (e) => {
      const spoken = e.results[0][0].transcript
      setText(spoken)
      setListening(false)
      setAutoFiring(true)
      autoFireTimer.current = setTimeout(() => {
        handleSubmit(spoken)
      }, 800)
    }

    recognition.onerror = () => {
      setListening(false)
      setAutoFiring(false)
    }
    recognition.onend = () => setListening(false)

    recognitionRef.current = recognition
    recognition.start()
    setListening(true)
  }

  // Labels per language
  const listeningLabel = { en: '● LISTENING', hi: '● सुन रहा हूं', mr: '● ऐकत आहे' }[lang] || '● LISTENING'
  const tapLabel       = { en: 'TAP TO SPEAK', hi: 'बोलने के लिए दबाएं', mr: 'बोलण्यासाठी दाबा' }[lang] || 'TAP TO SPEAK'
  const firingLabel    = { en: '⚡ EXECUTING', hi: '⚡ चला रहा हूं', mr: '⚡ चालवत आहे' }[lang] || '⚡ EXECUTING'

  const defaultPlaceholder = placeholder || {
    en: 'Type a command — e.g. Open Chrome, Search for Python...',
    hi: 'आदेश दें — जैसे Chrome खोलो, Discord लॉन्च करो...',
    mr: 'आदेश द्या — उदा. Chrome उघड, Discord सुरू कर...',
  }[lang] || 'Type a command...'

  const orbLabel = autoFiring ? firingLabel : listening ? listeningLabel : tapLabel
  const labelCls = autoFiring ? 'firing-label' : listening ? 'listening-label' : ''

  const orbEmoji = autoFiring ? '⚡' : listening ? '🎙️' : '🤖'

  return (
    <div className="voice-input-wrapper">
      <div className="orb-container">
        {/* Holographic orb */}
        <div className="orb-ring-outer">
          <div className="orb-ring-3" />
          <button
            id="voice-orb-btn"
            className={`orb-btn${listening ? ' listening' : ''}${autoFiring ? ' auto-firing' : ''}`}
            onClick={toggleVoice}
            title={listening ? 'Click to stop listening' : `Speak in ${voiceCode}`}
            aria-label="Voice command button"
          >
            {orbEmoji}
          </button>
        </div>

        {/* Waveform visualizer (shows when listening) */}
        <div className={`waveform${listening ? ' active' : ''}`}>
          {Array.from({ length: 9 }).map((_, i) => (
            <div key={i} className="wave-bar" />
          ))}
        </div>

        <span className={`orb-label${labelCls ? ` ${labelCls}` : ''}`}>{orbLabel}</span>
      </div>

      {/* Text input */}
      <div className="input-row">
        <input
          id="command-text-input"
          className={`cmd-input${autoFiring ? ' auto-firing-input' : ''}`}
          type="text"
          placeholder={defaultPlaceholder}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKey}
          disabled={isLoading}
          autoComplete="off"
          lang={voiceCode.split('-')[0]}
          spellCheck={false}
        />
        <button
          id="command-send-btn"
          className={`send-btn${autoFiring ? ' auto-firing-btn' : ''}`}
          onClick={() => handleSubmit()}
          disabled={!text.trim() || isLoading}
        >
          {isLoading
            ? <span className="loading-dots"><span/><span/><span/></span>
            : autoFiring ? '⚡' : 'EXECUTE'}
        </button>
      </div>
    </div>
  )
}
