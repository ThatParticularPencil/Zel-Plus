from __future__ import annotations

import json
from typing import Optional

from models.schemas import Incident, Message, Task
from services.llm_client import LLMClient


TASK_SYSTEM = """You generate operational tasks for a single frontline incident.

Return ONLY valid JSON:
{
  "tasks": [
    {
      "action": "...",
      "priority": "...",
      "parameters": {...}
    }
  ]
}

Rules:
- Generate 0 to 3 tasks
- action must be one of:
  dispatch, notify, resolve, escalate, log

- priority must be one of:
  low, medium, high

- parameters must be a JSON object with ONLY string keys and string values

Action meanings:
- dispatch = send someone to handle the issue
- notify = inform a manager or team
- escalate = serious, blocked, dangerous, or repeated issue
- resolve = incident is confirmed fixed
- log = record information only

No markdown.
No explanation.
No extra keys."""


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
        Task(action="log", priority="low", parameters={"role_hint": "unsure"}).model_dump(),
        Task(action="log", priority="low", parameters={"note": "unsure"}).model_dump(),
    ]
