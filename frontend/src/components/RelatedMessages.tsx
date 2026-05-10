import type { IncidentPayload } from '../types'

function formatTs(ts: number): string {
  const ms = ts < 1e12 ? ts * 1000 : ts
  const d = new Date(ms)
  if (Number.isNaN(d.getTime())) return String(ts)
  return d.toLocaleTimeString(undefined, { hour12: false })
}

export function RelatedMessages({ incident }: { incident: IncidentPayload }) {
  const msgs = incident.messages ?? []
  return (
    <ul className="space-y-2 font-mono text-[12px]">
      {msgs.map((m, i) => (
        <li key={i} className="border-l border-zinc-700 pl-2 text-zinc-400">
          <span className="text-zinc-600">[{formatTs(m.timestamp)}]</span>{' '}
          <span className="text-amber-700/80">{m.speaker}</span>
          <span className="block text-zinc-300">&quot;{m.message}&quot;</span>
        </li>
      ))}
    </ul>
  )
}
