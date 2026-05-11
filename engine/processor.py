from __future__ import annotations

import json
from typing import Any, Optional

from models.schemas import Message, ProcessedMessage
from services.llm_client import LLMClient


PROCESS_SYSTEM = """You extract structured fields from a single operational frontline message.

You MUST return ONLY valid JSON with EXACT keys:
event_type, urgency, topic, entities

DO NOT include any other keys, text, or formatting.

---

event_type must be EXACTLY one of:
- request (asking for help / action needed)
- report (describing an issue or observation)
- update (status progress, ongoing handling, partial fix)
- resolution (issue is confirmed fixed / completed / cleared)
- noise (non-operational, irrelevant, or non-actionable content)

---

STRICT RULES:
- Use "update" ONLY when work is actively being done or progress is being reported.
- Use "resolution" when the issue is explicitly fixed, cleared, or completed.
- If the message does not describe an operational state, set event_type = "noise".

---

urgency must be one of:
- low (informational or minor)
- medium (operationally relevant but not critical)
- high (blocking work, safety risk, or escalation language)


---

topic must be a stable snake_case identifier representing the physical operational context.

Rules:
- MUST be specific (include location/object if present)
- MUST NOT be generic ("message", "issue", "problem")
- MUST be reusable across related messages

Examples:
- dock_2_forklift_blockage
- aisle_4_locked_cabinet
- warehouse_loading_lane_delay

---

entities:
Return a JSON array of concise strings representing:
- physical locations
- equipment
- objects
- roles if relevant

DO NOT include generic words like "help", "issue", "problem".

Examples:
["dock 2", "forklift"]
["aisle 4", "cabinet"]

---

If the message is not operationally meaningful:
set event_type = "noise"
and keep other fields minimal.

Return ONLY JSON!!!.
"""

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
            raw_response=data if isinstance(data, dict) else {"response": data},
        )
    except Exception as exc:
        if allow_fallback:
            fallback = _fallback_processed(message)
            fallback.raw_response = {
                "fallback": True,
                "reason": "offline",
                "error": str(exc),
            }
            return fallback
        raise


def _fallback_processed(message: Message) -> ProcessedMessage:
    text = message.message.lower().strip()
    if len(text) < 2:
        return ProcessedMessage(
            event_type="noise",
            urgency="low",
            topic="empty",
            entities=[],
            raw_response={"fallback": True, "reason": "empty_message"},
        )

    if any(w in text for w in ("fixed", "resolved", "cleared", "done", "closed", "repaired")):
        return ProcessedMessage(
            event_type="resolution",
            urgency="medium",
            topic="unsure",
            entities=[],
            raw_response={"fallback": True, "reason": "offline_resolution"},
        )

    if any(w in text for w in ("dispatch", "dispatched", "assigned", "en route", "on site", "responding", "working", "progress", "ongoing", "still")):
        return ProcessedMessage(
            event_type="update",
            urgency="medium",
            topic="unsure",
            entities=[],
            raw_response={"fallback": True, "reason": "offline_update"},
        )

    if any(w in text for w in ("help", "need", "please", "urgent", "immediately", "asap", "assist", "support")):
        return ProcessedMessage(
            event_type="request",
            urgency="high",
            topic="unsure",
            entities=[],
            raw_response={"fallback": True, "reason": "offline_request"},
        )

    urgency = "high" if any(w in text for w in ("urgent", "emergency", "now", "immediately")) else "medium"
    return ProcessedMessage(
        event_type="report",
        urgency=urgency,
        topic="unsure",
        entities=[],
        raw_response={"fallback": True, "reason": "offline"},
    )
