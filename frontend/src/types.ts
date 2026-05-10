export type Urgency = 'low' | 'medium' | 'high'

export interface StreamMessage {
  id: string
  timestamp: number
  channel: string
  speaker: string
  message: string
  urgency: string
  intent: string
  topic?: string
  entities?: string[]
}

export interface SemanticRow {
  id: string
  timestamp: number
  channel: string
  speaker: string
  message: string
  intent: string
  urgency: string
  topic: string
  entities: string[]
}

export interface ClusterPreviewRow {
  channel: string
  cluster_id: string
  message_count: number
  emit_ready: boolean
  messages_needed_for_emit: number
  min_emit_threshold: number
}

export interface IncidentPayload {
  incident_id: string
  incident_type: string
  severity: string
  summary: string
  status: string
  messages: {
    channel: string
    timestamp: number
    speaker: string
    message: string
  }[]
  tasks: {
    action: string
    priority: string
    parameters: Record<string, unknown>
  }[]
}

export interface MemoryMatch {
  incident_type: string
  context_signature: string
  resolution: string
  outcome: string
  timestamp: number
}

export interface IncidentBundle {
  incident: IncidentPayload
  manager_summary: string
  memory_matches: MemoryMatch[]
}

export interface DashboardState {
  messages: StreamMessage[]
  semantic: SemanticRow[]
  incidents: IncidentBundle[]
  cluster_preview: ClusterPreviewRow[]
  emit_jobs_pending: number
}
