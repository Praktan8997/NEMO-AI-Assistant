const formatTime = (iso) => {
  try {
    return new Date(iso).toLocaleTimeString('en-US', { hour12: false })
  } catch {
    return '--:--'
  }
}

export default function CommandHistory({ history, onSelect }) {
  if (!history || history.length === 0) {
    return (
      <div style={{
        textAlign: 'center',
        padding: '24px 10px',
        color: 'var(--text-muted)',
        fontSize: '0.78rem',
        fontFamily: 'var(--font-hud)',
        letterSpacing: '0.05em',
      }}>
        <div style={{ fontSize: '1.3rem', marginBottom: 8, opacity: 0.4 }}>🕒</div>
        No commands yet
      </div>
    )
  }

  return (
    <div className="history-list" id="command-history-list">
      {history.map((item) => (
        <div
          key={item.command_id}
          className="history-item"
          onClick={() => onSelect?.(item)}
          title={item.response_text}
          id={`history-${item.command_id}`}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => e.key === 'Enter' && onSelect?.(item)}
        >
          <div className={`history-dot ${item.success ? 'success' : 'fail'}`} />
          <div className="history-text">
            <div className="history-cmd">{item.user_input}</div>
            <div className="history-intent">
              {item.intent?.replace(/_/g, ' ') ?? 'unknown'}
            </div>
          </div>
          <div className="history-time">{formatTime(item.timestamp)}</div>
        </div>
      ))}
    </div>
  )
}
