import type { IncidentBundle } from '../types'
import { RelatedMessages } from './RelatedMessages'
import { SummaryBox } from './SummaryBox'
import { TaskList } from './TaskList'

export function IncidentDetail({ bundle }: { bundle: IncidentBundle | null }) {
  if (!bundle) {
    return (
      <section className="flex min-h-0 flex-1 flex-col border border-zinc-800 bg-[#08090b]">
        <header className="shrink-0 border-b border-zinc-800 px-3 py-2 font-mono text-[11px] uppercase tracking-wide text-zinc-500">
          Incident detail
        </header>
        <div className="flex flex-1 items-center justify-center p-4 font-mono text-[12px] text-zinc-600">
          Select an incident
        </div>
      </section>
    )
  }

  const inc = bundle.incident
  const memories = bundle.memory_matches ?? []

  return (
    <section className="flex min-h-0 flex-1 flex-col border border-zinc-800 bg-[#08090b]">
      <header className="shrink-0 border-b border-zinc-800 px-3 py-2 font-mono text-[11px] uppercase tracking-wide text-zinc-500">
        Incident detail · {inc.incident_id}
      </header>
      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-3 py-3">
        <div>
          <h3 className="mb-1 font-mono text-[10px] uppercase tracking-wide text-zinc-500">Summary</h3>
          <SummaryBox text={inc.summary} />
        </div>
        <div>
          <h3 className="mb-1 font-mono text-[10px] uppercase tracking-wide text-zinc-500">Tasks</h3>
          <TaskList incident={inc} />
        </div>
        <div>
          <h3 className="mb-1 font-mono text-[10px] uppercase tracking-wide text-zinc-500">
            Related messages
          </h3>
          <RelatedMessages incident={inc} />
        </div>
        {memories.length > 0 && (
          <div>
            <h3 className="mb-1 font-mono text-[10px] uppercase tracking-wide text-zinc-500">
              Similar historical incidents
            </h3>
            <ul className="space-y-1 font-mono text-[12px] text-zinc-400">
              {memories.map((m, i) => (
                <li key={i} className="border-l border-zinc-700 pl-2">
                  {m.incident_type} → {m.resolution}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </section>
  )
}
