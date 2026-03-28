const AGENT_META = [
  { key: 'AI Agent',         emoji: '🧠', cls: 'ai',      role: 'NLP & Intent Recognition' },
  { key: 'UI Agent',         emoji: '🖥️', cls: 'ui',      role: 'React/Vite Interface' },
  { key: 'Automation Agent', emoji: '⚙️', cls: 'auto',    role: 'System Command Execution' },
  { key: 'Backend Agent',    emoji: '🔗', cls: 'backend', role: 'FastAPI Orchestration' },
  { key: 'Debug Agent',      emoji: '🐛', cls: 'debug',   role: 'Logging & Health Monitor' },
]

const STATUS_BADGE = {
  idle:       'badge-idle',
  processing: 'badge-processing',
  success:    'badge-success',
  error:      'badge-error',
}

const STATUS_LABEL = {
  idle:       'IDLE',
  processing: 'ACTIVE',
  success:    'READY',
  error:      'ERROR',
}

export default function AgentStatus({ agents }) {
  return (
    <div className="agent-list">
      {AGENT_META.map(({ key, emoji, cls, role }) => {
        const info   = agents?.find((a) => a.name === key)
        const status = info?.status ?? 'idle'
        const tasks  = info?.tasks_completed ?? 0
        return (
          <div
            key={key}
            className={`agent-card status-${status}`}
            id={`agent-card-${cls}`}
          >
            <div className={`agent-avatar ${cls}`}>{emoji}</div>
            <div className="agent-info">
              <div className="agent-name">{key}</div>
              <div className="agent-role">{role} · {tasks} tasks</div>
            </div>
            <span className={`agent-status-badge ${STATUS_BADGE[status] ?? 'badge-idle'}`}>
              {STATUS_LABEL[status] ?? status.toUpperCase()}
            </span>
          </div>
        )
      })}
    </div>
  )
}
