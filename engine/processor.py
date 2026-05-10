from __future__ import annotations

import json
from typing import Optional

from models.schemas import Message, ProcessedMessage
from services.llm_client import LLMClient


PROCESS_SYSTEM = """You extract structured fields from a single operational frontline message.
Return ONLY a JSON object with keys: intent, urgency, topic, entities.
intent must be one of: request, report, update, none, noise.
urgency must be one of: low, medium, high.
topic is a short snake_case or plain phrase describing the subject.
entities is a JSON array of short strings (people, places, objects).
If the message is ambiguous or not actionable, set intent to "noise".
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
            intent=str(data.get("intent", "noise")),
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
        return ProcessedMessage(intent="noise", urgency="low", topic="empty", entities=[])
    urgency = "high" if any(w in text for w in ("urgent", "emergency", "now", "immediately")) else "medium"
    return ProcessedMessage(
        intent="report",
        urgency=urgency,
        topic="frontline_message",
        entities=[],
    )
