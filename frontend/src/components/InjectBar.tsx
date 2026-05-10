import { useCallback, useState } from 'react'

function apiBase(): string {
  return import.meta.env.VITE_API_BASE ?? ''
}

const LS_CH = 'zel_inject_channel'
const LS_SP = 'zel_inject_speaker'

export function InjectBar({
  disabled,
  onSent,
}: {
  disabled: boolean
  onSent: () => void
}) {
  const [channel, setChannel] = useState(() => localStorage.getItem(LS_CH) ?? 'sim_channel')
  const [speaker, setSpeaker] = useState(() => localStorage.getItem(LS_SP) ?? 'worker_1')
  const [message, setMessage] = useState('')
  const [sending, setSending] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const send = useCallback(async () => {
    const text = message.trim()
    if (!text || disabled || sending) return
    setSending(true)
    setErr(null)
    try {
      localStorage.setItem(LS_CH, channel)
      localStorage.setItem(LS_SP, speaker)
      const r = await fetch(`${apiBase()}/ingest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          channel: channel.trim() || 'sim_channel',
          speaker: speaker.trim() || 'operator',
          timestamp: Math.floor(Date.now() / 1000),
          message: text,
        }),
      })
      if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
      setMessage('')
      onSent()
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'send failed')
    } finally {
      setSending(false)
    }
  }, [channel, speaker, message, disabled, sending, onSent])

  return (
    <div className="shrink-0 border-t border-zinc-800 bg-[#0f1014] px-2 py-2">
      <div className="mb-1.5 flex flex-wrap gap-1.5 font-mono text-[11px]">
        <input
          aria-label="Channel"
          className="min-w-[7rem] flex-1 border border-zinc-700 bg-zinc-950 px-2 py-1 text-zinc-200 outline-none focus:border-zinc-500"
          value={channel}
          onChange={(e) => setChannel(e.target.value)}
          placeholder="channel"
          disabled={disabled}
        />
        <input
          aria-label="Speaker"
          className="min-w-[6rem] flex-1 border border-zinc-700 bg-zinc-950 px-2 py-1 text-zinc-200 outline-none focus:border-zinc-500"
          value={speaker}
          onChange={(e) => setSpeaker(e.target.value)}
          placeholder="speaker"
          disabled={disabled}
        />
      </div>
      <div className="flex gap-1.5">
        <input
          aria-label="Message"
          className="min-w-0 flex-1 border border-zinc-700 bg-zinc-950 px-2 py-1.5 font-mono text-[12px] text-zinc-200 outline-none focus:border-zinc-500"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="Type message → Enter or Send"
          disabled={disabled || sending}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              void send()
            }
          }}
        />
        <button
          type="button"
          onClick={() => void send()}
          disabled={disabled || sending || !message.trim()}
          className="shrink-0 border border-amber-900/60 bg-amber-950/40 px-3 py-1.5 font-mono text-[11px] uppercase tracking-wide text-amber-200/90 hover:bg-amber-950/70 disabled:opacity-40"
        >
          {sending ? '…' : 'Send'}
        </button>
      </div>
      {err && <p className="mt-1 font-mono text-[10px] text-red-400">{err}</p>}
    </div>
  )
}
