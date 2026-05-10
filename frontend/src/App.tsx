import { useEffect, useMemo, useRef, useState } from 'react'
import { IncidentDetail } from './components/IncidentDetail'
import { IncidentPanel } from './components/IncidentPanel'
import { InjectBar } from './components/InjectBar'
import { Layout } from './components/Layout'
import { MessageFeed } from './components/MessageFeed'
import { useDashboardPoll } from './hooks/useDashboardPoll'
import type { IncidentBundle } from './types'

export default function App() {
  const { state, error, refetch } = useDashboardPoll(1500)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const prevIncidentCount = useRef(0)

  const incidents = state.incidents ?? []

  useEffect(() => {
    if (incidents.length === 0) {
      prevIncidentCount.current = 0
      setSelectedId(null)
      return
    }
    const newest = incidents[incidents.length - 1].incident.incident_id
    const grew = incidents.length > prevIncidentCount.current
    prevIncidentCount.current = incidents.length

    setSelectedId((prev) => {
      if (prev === null) return newest
      const stillThere = incidents.some((b) => b.incident.incident_id === prev)
      if (!stillThere) return newest
      if (grew) return newest
      return prev
    })
  }, [incidents])

  const selectedBundle: IncidentBundle | null = useMemo(() => {
    if (!selectedId) return null
    return incidents.find((b) => b.incident.incident_id === selectedId) ?? null
  }, [incidents, selectedId])

  return (
    <Layout
      header={
        <header className="flex shrink-0 items-center justify-between border-b border-zinc-800 bg-[#0f1014] px-4 py-2">
          <div>
            <h1 className="font-mono text-[13px] font-medium tracking-tight text-zinc-200">
              Zel+ · Incident Intelligence
            </h1>
            <p className="font-mono text-[11px] text-zinc-500">
              raw feed → clustering → incidents → tasks & summary
            </p>
          </div>
          <div className="flex items-center gap-3 font-mono text-[11px]">
            {error ? (
              <span className="text-red-400" title={error}>
                backend offline
              </span>
            ) : (
              <span className="flex items-center gap-1.5 text-emerald-600/90">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-500" />
                live poll 1.5s
              </span>
            )}
          </div>
        </header>
      }
    >
      <div className="flex min-h-0 min-w-0 flex-col lg:min-h-[calc(100vh-3rem)]">
        <MessageFeed messages={state.messages} />
        <InjectBar disabled={!!error} onSent={() => void refetch()} />
      </div>
      <IncidentPanel
        incidents={incidents}
        selectedId={selectedId}
        onSelect={(id) => setSelectedId(id)}
      />
      <IncidentDetail bundle={selectedBundle} />
    </Layout>
  )
}
