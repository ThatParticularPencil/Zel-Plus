export type Urgency = 'low' | 'medium' | 'high'

export interface StreamMessage {
  id: string
  timestamp: number
  channel: string
  speaker: string
  message: string
  urgency: string
  event_type: string
  topic?: string
  entities?: string[]
}

export interface SemanticRow {
  id: string
  timestamp: number
  channel: string
  speaker: string
  message: string
  event_type: string
  urgency: string
  topic: string
  entities: string[]
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
}
