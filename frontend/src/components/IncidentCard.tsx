import type { IncidentBundle } from '../types'

function severityStyle(s: string): string {
  const x = s.toLowerCase()
  if (x === 'high') return 'text-red-400'
  if (x === 'medium') return 'text-yellow-400'
  return 'text-zinc-400'
}

function statusLabel(status: string): string {
  return status.toUpperCase()
}

export function IncidentCard({
  bundle,
  selected,
  onSelect,
}: {
  bundle: IncidentBundle
  selected: boolean
  onSelect: () => void
}) {
  const inc = bundle.incident
  const n = inc.messages?.length ?? 0

  return (
    <button
      type="button"
      onClick={onSelect}
      className={`w-full border px-2.5 py-2 text-left font-mono text-[12px] transition-colors ${
        selected
          ? 'border-amber-900/80 bg-amber-950/30'
          : 'border-zinc-800 bg-zinc-900/40 hover:border-zinc-700'
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="text-amber-600/90">{inc.incident_id}</span>
        <span className={`shrink-0 ${severityStyle(inc.severity)}`}>{inc.severity.toUpperCase()}</span>
      </div>
      <div className="mt-1 line-clamp-2 text-zinc-300">{inc.incident_type.replace(/_/g, ' ')}</div>
      <div className="mt-2 flex justify-between text-[11px] text-zinc-500">
        <span>{n} related messages</span>
        <span>{statusLabel(inc.status)}</span>
      </div>
    </button>
  )
}
