import type { ClusterPreviewRow } from '../types'

export function PipelineStrip({
  pending,
  preview,
}: {
  pending: number
  preview: ClusterPreviewRow[]
}) {
  const tail = preview.slice(-4)
  return (
    <div className="shrink-0 border-b border-zinc-800 bg-[#0a0b0e] px-3 py-1.5 font-mono text-[10px] text-zinc-500">
      <span className="text-zinc-400">pipeline</span>
      {pending > 0 && (
        <span className="ml-3 text-amber-600/90">
          incident LLMs running ({pending})
        </span>
      )}
      {pending === 0 && <span className="ml-3 text-zinc-600">incident queue idle</span>}
      {tail.length > 0 && (
        <span className="ml-3 block truncate text-zinc-500 sm:inline sm:truncate">
          clusters:{' '}
          {tail
            .map(
              (p) =>
                `${p.channel}:${p.message_count}/${p.min_emit_threshold}${p.emit_ready ? '✓' : ''}`,
            )
            .join(' · ')}
        </span>
      )}
    </div>
  )
}
