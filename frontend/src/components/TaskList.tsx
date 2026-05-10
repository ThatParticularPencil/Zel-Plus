import type { IncidentPayload } from '../types'

export function TaskList({ incident }: { incident: IncidentPayload }) {
  const tasks = incident.tasks ?? []
  if (tasks.length === 0) {
    return <p className="font-mono text-[12px] text-zinc-600">No tasks.</p>
  }
  return (
    <ul className="list-none space-y-1.5 font-mono text-[13px] text-zinc-300">
      {tasks.map((t, i) => (
        <li key={i} className="flex gap-2 border-l-2 border-zinc-700 pl-2">
          <span className="shrink-0 text-zinc-500">{t.action}</span>
          <span className="text-zinc-400">
            {Object.entries(t.parameters || {})
              .map(([k, v]) => `${k}=${String(v)}`)
              .join(' · ') || '—'}
          </span>
        </li>
      ))}
    </ul>
  )
}
