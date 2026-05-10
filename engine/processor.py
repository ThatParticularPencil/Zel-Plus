from __future__ import annotations

import json
from typing import Optional

from models.schemas import Message, ProcessedMessage
from services.llm_client import LLMClient


PROCESS_SYSTEM = """You extract structured fields from a single operational frontline message.
Return ONLY a JSON object with keys: event_type, urgency, topic, entities.
event_type must be one of: request, report, update, resolution, noise.
Use event_type "update" when the speaker is confirming progress, providing a status update, or describing a fix.
Use event_type "resolution" when the message indicates the issue is resolved or cleared.
urgency must be one of: low, medium, high.
topic must be a short stable snake_case slug tied to the physical situation (e.g. cabinet_aisle_4, dock_3_spill), not generic words like "message" or "issue".
entities is a JSON array of short strings (people, places, objects).
If the message is ambiguous or not actionable, set event_type to "noise".
No markdown, no explanation, no extra keys."""


def process_message_llm(
    client: Optional[LLMClient],
    message: Message,
    *,
    allow_fallback: bool = True,
) -> ProcessedMessage:
    if client is None:
        return _fallback_processed(message)
    user = json.dumps(
        {
            "channel": message.channel,
            "timestamp": message.timestamp,
            "speaker": message.speaker,
            "message": message.message,
        },
        ensure_ascii=False,
    )
    try:
        data = client.complete_json(PROCESS_SYSTEM, user)
        return ProcessedMessage(
            event_type=str(data.get("event_type", "noise")),
            urgency=str(data.get("urgency", "low")),
            topic=str(data.get("topic", "general")),
            entities=list(data.get("entities") or []),
        )
    except Exception:
        if allow_fallback:
            return _fallback_processed(message)
        raise


def _fallback_processed(message: Message) -> ProcessedMessage:
    text = message.message.lower().strip()
    if len(text) < 2:
        return ProcessedMessage(event_type="noise", urgency="low", topic="empty", entities=[])
    urgency = "high" if any(w in text for w in ("urgent", "emergency", "now", "immediately")) else "medium"
    return ProcessedMessage(
        event_type="report",
        urgency=urgency,
        topic="frontline_message",
        entities=[],
    )
