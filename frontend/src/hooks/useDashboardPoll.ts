import { useCallback, useEffect, useState } from 'react'
import type { DashboardState } from '../types'

const empty: DashboardState = { messages: [], incidents: [] }

function apiBase(): string {
  return import.meta.env.VITE_API_BASE ?? ''
}

export function useDashboardPoll(intervalMs = 1500) {
  const [state, setState] = useState<DashboardState>(empty)
  const [error, setError] = useState<string | null>(null)

  const fetchState = useCallback(async () => {
    try {
      const r = await fetch(`${apiBase()}/dashboard/state`)
      if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
      const data = (await r.json()) as DashboardState
      setState(data)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'fetch failed')
    }
  }, [])

  useEffect(() => {
    void fetchState()
    const id = window.setInterval(() => void fetchState(), intervalMs)
    return () => window.clearInterval(id)
  }, [fetchState, intervalMs])

  return { state, error, refetch: fetchState }
}
