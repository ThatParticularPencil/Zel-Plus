import { useEffect, useMemo, useRef, useState } from 'react'
import { IncidentDetail } from './components/IncidentDetail'
import { IncidentPanel } from './components/IncidentPanel'
import { InjectBar } from './components/InjectBar'
import { Layout } from './components/Layout'
import { MessageFeed } from './components/MessageFeed'
import { PipelineStrip } from './components/PipelineStrip'
import { SemanticFeed } from './components/SemanticFeed'
import { useDashboardPoll } from './hooks/useDashboardPoll'
import type { IncidentBundle } from './types'

export default function App() {
  const { state, error, refetch } = useDashboardPoll(400)
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

  const burstRefetch = () => {
    void refetch()
  }

  return (
    <Layout
      header={
        <>
          <header className="flex shrink-0 items-center justify-between border-b border-zinc-800 bg-[#0f1014] px-4 py-2">
            <div>
              <h1 className="font-mono text-[13px] font-medium tracking-tight text-zinc-200">
                Zel+ · Incident Intelligence
              </h1>
              <p className="font-mono text-[11px] text-zinc-500">
                raw → semantics → cluster → incidents → tasks
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
                  poll 400ms · ingest returns fast
                </span>
              )}
            </div>
          </header>
          <PipelineStrip
            pending={state.emit_jobs_pending}
            preview={state.cluster_preview}
          />
        </>
      }
    >
      <div className="flex min-h-0 min-w-0 flex-col border-zinc-800 lg:col-span-2 lg:border-b xl:col-span-1 xl:border-b-0 xl:border-r">
        <MessageFeed messages={state.messages} />
        <InjectBar disabled={!!error} onSent={burstRefetch} />
      </div>
      <div className="flex min-h-0 min-w-0 flex-col border-zinc-800 lg:border-r xl:border-r-0">
        <SemanticFeed rows={state.semantic} />
      </div>
      <div className="flex min-h-0 min-w-0 flex-col border-zinc-800 lg:border-r xl:border-r-0">
        <IncidentPanel
          incidents={incidents}
          selectedId={selectedId}
          onSelect={(id) => setSelectedId(id)}
        />
      </div>
      <div className="flex min-h-0 min-w-0 flex-col">
        <IncidentDetail bundle={selectedBundle} />
      </div>
    </Layout>
  )
}
