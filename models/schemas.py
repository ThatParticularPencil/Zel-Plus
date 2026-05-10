from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class Message(BaseModel):
    channel: str
    timestamp: int
    speaker: str
    message: str


class ProcessedMessage(BaseModel):
    event_type: str
    urgency: str  # low | medium | high
    topic: str
    entities: list[str]


class Task(BaseModel):
    action: str
    priority: str
    parameters: dict


class Incident(BaseModel):
    incident_id: str
    incident_type: str
    severity: str
    summary: str
    status: str  # active | resolved
    entities: list[str] = []
    messages: list[Message]
    tasks: list[dict]
    created_at: int = 0
    updated_at: int = 0


class MemoryEntry(BaseModel):
    incident_type: str
    context_signature: str
    resolution: str
    outcome: str
    timestamp: int


class ClusterMeta(BaseModel):
    """Cluster output shape from clustering step."""

    incident_id: str
    message_ids: list[str] = Field(default_factory=list)


class IncidentConstructionResult(BaseModel):
    incident_type: str
    severity: str
    summary: str
    location: Optional[str] = None


class TaskGenerationResult(BaseModel):
    tasks: list[dict]
