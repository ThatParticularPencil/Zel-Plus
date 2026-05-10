import { useEffect, useRef } from 'react'
import type { StreamMessage } from '../types'
import { MessageCard } from './MessageCard'

export function MessageFeed({ messages }: { messages: StreamMessage[] }) {
  const bottom = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length])

  return (
    <section className="flex min-h-0 flex-1 flex-col border border-zinc-800 bg-[#08090b]">
      <header className="shrink-0 border-b border-zinc-800 px-3 py-2 font-mono text-[11px] uppercase tracking-wide text-zinc-500">
        Message stream
      </header>
      <div className="min-h-0 flex-1 space-y-2 overflow-y-auto px-2 py-2">
        {messages.length === 0 && (
          <p className="px-1 py-6 font-mono text-[12px] text-zinc-600">
            No messages yet. POST to <code className="text-zinc-400">/ingest</code> (see API docs).
          </p>
        )}
        {messages.map((m) => (
          <MessageCard key={m.id} m={m} />
        ))}
        <div ref={bottom} />
      </div>
    </section>
  )
}
