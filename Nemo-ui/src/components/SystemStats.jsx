export default function SystemStats({ health }) {
  if (!health) {
    return (
      <div style={{ textAlign: 'center', padding: '22px', color: 'var(--text-muted)', fontSize: '0.78rem', fontFamily: 'var(--font-hud)' }}>
        <div style={{ fontSize: '1.4rem', marginBottom: 8, opacity: 0.5 }}>📡</div>
        Connecting to backend…
      </div>
    )
  }

  const uptime = health.system_uptime ?? 0
  const hours   = Math.floor(uptime / 3600)
  const minutes = Math.floor((uptime % 3600) / 60)
  const seconds = Math.floor(uptime % 60)
  const uptimeStr = `${String(hours).padStart(2,'0')}:${String(minutes).padStart(2,'0')}:${String(seconds).padStart(2,'0')}`

  const totalAgents  = health.agents?.length ?? 0
  const activeAgents = health.agents?.filter(a => a.status === 'success' || a.status === 'processing').length ?? 0
  const totalTasks   = health.agents?.reduce((s, a) => s + (a.tasks_completed ?? 0), 0) ?? 0
  const totalCmds    = health.total_commands_processed ?? 0

  const stats = [
    {
      value: totalCmds,
      label: 'Commands',
      fill: 'fill-cyan',
      fillPct: Math.min(totalCmds * 5, 100),
    },
    {
      value: totalAgents,
      label: 'Agents',
      fill: 'fill-purple',
      fillPct: totalAgents > 0 ? (activeAgents / totalAgents) * 100 : 0,
    },
    {
      value: uptimeStr,
      label: 'Uptime',
      fill: 'fill-green',
      fillPct: 100,
      small: true,
    },
    {
      value: totalTasks,
      label: 'Tasks Done',
      fill: 'fill-amber',
      fillPct: Math.min(totalTasks * 4, 100),
    },
  ]

  return (
    <div className="stats-grid" id="system-stats-grid">
      {stats.map(({ value, label, fill, fillPct, small }) => (
        <div className="stat-item" key={label}>
          <div className="stat-value" style={small ? { fontSize: '1rem' } : {}}>
            {value}
          </div>
          <div className="stat-label">{label}</div>
          <div className="stat-bar">
            <div className={`stat-bar-fill ${fill}`} style={{ width: `${fillPct}%` }} />
          </div>
        </div>
      ))}
    </div>
  )
}
