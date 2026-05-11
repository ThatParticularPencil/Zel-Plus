from __future__ import annotations

import json
from typing import Optional

from models.schemas import Incident
from services.llm_client import LLMClient


SUMMARY_SYSTEM = """Write one concise operational summary of the incident. 
Add detail with .md bullet points ONLY IF NECESSARY
include speaker and channel
DONT INCLUDE EXTRA INFO LIKE INCIDENT ID"""


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
        parts.append("unsure")
    return " ".join(parts)
