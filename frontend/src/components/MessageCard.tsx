import type { StreamMessage } from '../types'

function urgencyBorder(u: string): string {
  switch (u) {
    case 'high':
      return 'border-l-red-500'
    case 'medium':
      return 'border-l-yellow-500'
    default:
      return 'border-l-zinc-600'
  }
}

function formatTs(ts: number): string {
  const ms = ts < 1e12 ? ts * 1000 : ts
  const d = new Date(ms)
  if (Number.isNaN(d.getTime())) return String(ts)
  return d.toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

export function MessageCard({ m }: { m: StreamMessage }) {
  return (
    <article
      className={`border border-zinc-800 border-l-4 ${urgencyBorder(m.urgency)} bg-zinc-900/50 px-2.5 py-2 text-[13px] leading-snug`}
    >
      <div className="mb-1 flex items-baseline justify-between gap-2 font-mono text-[11px] text-zinc-500">
        <span>[{formatTs(m.timestamp)}]</span>
        <span className="truncate text-zinc-400">{m.channel}</span>
      </div>
      <div className="font-mono text-[12px] text-amber-700/90">{m.speaker}</div>
      <p className="mt-1 text-zinc-200">&quot;{m.message}&quot;</p>
    </article>
  )
}
