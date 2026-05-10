from __future__ import annotations

import json
from typing import Optional

from engine.message_ingestor import BufferedMessage
from models.schemas import IncidentConstructionResult, Message
from services.llm_client import LLMClient


BUILD_SYSTEM = """You synthesize one operational incident from clustered frontline messages.
Return ONLY JSON with keys: incident_type, severity, summary, location.
severity must be one of: low, medium, high.
location may be a short string or null if unknown.
incident_type is a short snake_case label.
summary is one or two sentences describing what happened.
No markdown, no explanation, no extra keys."""


def build_incident_llm(
    client: Optional[LLMClient],
    cluster_buffers: list[BufferedMessage],
    *,
    allow_fallback: bool = True,
) -> IncidentConstructionResult:
    messages = [b.message for b in cluster_buffers]
    if client is None:
        return _fallback_build(messages)
    payload = {
        "messages": [m.model_dump() for m in messages],
        "processed": [
            {
                "internal_id": b.internal_id,
                "event_type": b.processed.event_type,
                "urgency": b.processed.urgency,
                "topic": b.processed.topic,
                "entities": b.processed.entities,
            }
            for b in cluster_buffers
            if b.processed
        ],
    }
    user = json.dumps(payload, ensure_ascii=False)
    try:
        data = client.complete_json(BUILD_SYSTEM, user)
        return IncidentConstructionResult(
            incident_type=str(data.get("incident_type", "general")),
            severity=str(data.get("severity", "medium")),
            summary=str(data.get("summary", "")),
            location=data.get("location"),
        )
    except Exception:
        if allow_fallback:
            return _fallback_build(messages)
        raise


def _fallback_build(messages: list[Message]) -> IncidentConstructionResult:
    first = messages[0].message if messages else ""
    return IncidentConstructionResult(
        incident_type="operational_event",
        severity="medium",
        summary=first[:500] or "Operational incident reported.",
        location=None,
    )
