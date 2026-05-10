import { useEffect, useRef } from 'react'
import type { SemanticRow } from '../types'

function intentTone(intent: string): string {
  if (intent === 'noise') return 'text-zinc-600'
  return 'text-sky-600/90'
}

export function SemanticFeed({ rows }: { rows: SemanticRow[] }) {
  const bottom = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: 'smooth' })
  }, [rows.length])

  return (
    <section className="flex h-full min-h-0 flex-1 flex-col border border-zinc-800 bg-[#08090b]">
      <header className="shrink-0 border-b border-zinc-800 px-3 py-2 font-mono text-[11px] uppercase tracking-wide text-zinc-500">
        Semantic layer (LLM #1)
      </header>
      <div className="min-h-0 flex-1 space-y-2 overflow-y-auto px-2 py-2">
        {rows.length === 0 && (
          <p className="px-1 py-6 font-mono text-[12px] text-zinc-600">
            Processed intent / topic / entities appear here as soon as each message is ingested.
          </p>
        )}
        {rows.map((r) => (
          <article
            key={r.id}
            className="border border-zinc-800 bg-zinc-900/40 px-2.5 py-2 font-mono text-[12px] leading-snug"
          >
            <div className="mb-1 flex flex-wrap gap-x-2 gap-y-0.5 text-[11px] text-zinc-500">
              <span>{r.channel}</span>
              <span className={intentTone(r.intent)}>intent:{r.intent}</span>
              <span className="text-zinc-400">urgency:{r.urgency}</span>
            </div>
            <div className="text-[11px] text-emerald-700/90">topic: {r.topic}</div>
            {(r.entities?.length ?? 0) > 0 && (
              <div className="mt-1 text-[11px] text-zinc-500">
                entities: {r.entities.join(', ')}
              </div>
            )}
            <p className="mt-1 line-clamp-3 text-zinc-300">&quot;{r.message}&quot;</p>
          </article>
        ))}
        <div ref={bottom} />
      </div>
    </section>
  )
}
