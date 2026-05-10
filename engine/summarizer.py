from __future__ import annotations

import json
from typing import Optional

from models.schemas import Incident
from services.llm_client import LLMClient


SUMMARY_SYSTEM = """Write one concise operational paragraph summarizing the incident and planned tasks for a manager.
Plain text only: no JSON, no markdown headings, no bullet lists."""


def generate_summary_llm(
    client: Optional[LLMClient],
    incident: Incident,
    *,
    allow_fallback: bool = True,
) -> str:
    payload = {"incident": incident.model_dump()}
    user = json.dumps(payload, ensure_ascii=False)
    if client is None:
        return _fallback_summary(incident)
    try:
        text = client.complete_text(SUMMARY_SYSTEM, user)
        return text.strip() or _fallback_summary(incident)
    except Exception:
        if allow_fallback:
            return _fallback_summary(incident)
        raise


def _fallback_summary(incident: Incident) -> str:
    parts = [incident.summary]
    if incident.tasks:
        parts.append("Actions queued for follow-up.")
    return " ".join(parts)
