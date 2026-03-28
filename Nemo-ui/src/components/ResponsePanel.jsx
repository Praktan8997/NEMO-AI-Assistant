export default function ResponsePanel({ response, isLoading }) {
  if (isLoading) {
    return (
      <div className="response-content">
        <div className="response-empty">
          <div style={{ fontSize: '2.5rem', marginBottom: 16 }}>
            <span className="loading-dots">
              <span/><span/><span/>
            </span>
          </div>
          <div style={{ color: 'var(--accent-cyan)', fontFamily: 'var(--font-display)', fontSize: '0.72rem', letterSpacing: '0.2em' }}>
            AGENTS PROCESSING…
          </div>
        </div>
      </div>
    )
  }

  if (!response) {
    return (
      <div className="response-content">
        <div className="response-empty">
          <div className="response-empty-icon">💬</div>
          <p>Jarvis is standing by.</p>
          <p style={{ marginTop: 8, fontSize: '0.75rem' }}>Type or speak a command above.</p>
        </div>
      </div>
    )
  }

  const { nlp_result, automation_result, response_text, agents_involved, command_id } = response
  const isError = !automation_result?.success

  return (
    <div className="response-content">
      <div className={`response-card ${isError ? 'error-card' : ''}`}>
        <div className={`response-badge ${isError ? 'error-badge' : ''}`}>
          {isError ? '❌ ERROR' : '✅ EXECUTED'} · {command_id}
        </div>
        <p className="response-text">{response_text}</p>

        {nlp_result && (
          <>
            <div className="confidence-bar-wrap">
              <span className="confidence-label">CONFIDENCE</span>
              <div className="confidence-bar">
                <div
                  className="confidence-fill"
                  style={{ width: `${Math.round((nlp_result.confidence ?? 0) * 100)}%` }}
                />
              </div>
              <span className="confidence-label">
                {Math.round((nlp_result.confidence ?? 0) * 100)}%
              </span>
            </div>

            <div className="response-meta">
              <span className="meta-tag">🎯 {nlp_result.intent?.replace(/_/g, ' ').toUpperCase()}</span>
              {Object.entries(nlp_result.entities ?? {}).map(([k, v]) => (
                <span key={k} className="meta-tag">
                  {k}: {String(v)}
                </span>
              ))}
              {(agents_involved ?? []).map((a) => (
                <span key={a} className="meta-tag">🤖 {a}</span>
              ))}
            </div>
          </>
        )}

        {automation_result?.output && (
          <div style={{
            marginTop: 14,
            padding: '10px 14px',
            background: 'rgba(0,212,255,0.04)',
            border: '1px solid var(--border-dim)',
            borderRadius: 'var(--radius-sm)',
            fontFamily: 'monospace',
            fontSize: '0.8rem',
            color: 'var(--text-dim)',
            lineHeight: 1.6,
          }}>
            {automation_result.output}
          </div>
        )}
      </div>
    </div>
  )
}
