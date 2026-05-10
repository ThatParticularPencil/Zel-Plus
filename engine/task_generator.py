from __future__ import annotations

import json
from typing import Optional

from models.schemas import Incident, Message, Task
from services.llm_client import LLMClient


TASK_SYSTEM = """You propose up to 3 abstract operational tasks for an incident.
Return ONLY JSON: {"tasks": [{"action","priority","parameters"}]}.
action must be one of: dispatch, notify, resolve, escalate, log.
priority must be one of: low, medium, high.
parameters is a JSON object with simple string keys (e.g. role_hint, area).
Do not reference external systems, vendors, or APIs.
No markdown, no explanation, no extra keys."""


def generate_tasks_llm(
    client: Optional[LLMClient],
    incident: Incident,
    messages: list[Message],
    severity: str,
    rag_block: str,
    *,
    allow_fallback: bool = True,
) -> list[dict]:
    if client is None:
        return _fallback_tasks(severity)
    payload = {
        "incident": incident.model_dump(),
        "messages": [m.model_dump() for m in messages],
        "severity": severity,
        "similar_past_incidents": rag_block,
    }
    user = json.dumps(payload, ensure_ascii=False)
    try:
        data = client.complete_json(TASK_SYSTEM, user)
        tasks_raw = data.get("tasks") or []
        out: list[dict] = []
        for t in tasks_raw[:3]:
            if not isinstance(t, dict):
                continue
            task = Task(
                action=str(t.get("action", "log")),
                priority=str(t.get("priority", "medium")),
                parameters=dict(t.get("parameters") or {}),
            )
            out.append(task.model_dump())
        return out or _fallback_tasks(severity)
    except Exception:
        if allow_fallback:
            return _fallback_tasks(severity)
        raise


def _fallback_tasks(severity: str) -> list[dict]:
    pri = severity if severity in ("low", "medium", "high") else "medium"
    return [
        Task(action="dispatch", priority=pri, parameters={"role_hint": "floor_associate"}).model_dump(),
        Task(action="log", priority="low", parameters={"note": "record_incident"}).model_dump(),
    ]
