import type { IncidentBundle } from '../types'
import { IncidentCard } from './IncidentCard'

export function IncidentPanel({
  incidents,
  selectedId,
  onSelect,
}: {
  incidents: IncidentBundle[]
  selectedId: string | null
  onSelect: (id: string) => void
}) {
  return (
    <section className="flex min-h-0 flex-1 flex-col border border-zinc-800 bg-[#08090b]">
      <header className="shrink-0 border-b border-zinc-800 px-3 py-2 font-mono text-[11px] uppercase tracking-wide text-zinc-500">
        Active incidents
      </header>
      <div className="min-h-0 flex-1 space-y-2 overflow-y-auto px-2 py-2">
        {incidents.length === 0 && (
          <p className="px-1 py-6 font-mono text-[12px] text-zinc-600">
            Incidents appear when messages create or update them immediately.
          </p>
        )}
        {[...incidents].reverse().map((b) => (
          <IncidentCard
            key={b.incident.incident_id}
            bundle={b}
            selected={selectedId === b.incident.incident_id}
            onSelect={() => onSelect(b.incident.incident_id)}
          />
        ))}
      </div>
    </section>
  )
}
