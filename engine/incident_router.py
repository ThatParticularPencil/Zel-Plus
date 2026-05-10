from __future__ import annotations

import time
import uuid
from typing import Optional

from engine.memory import IncidentStore
from engine.resolution_routing import append_resolution_note
from engine.summarizer import generate_summary_llm
from engine.task_generator import generate_tasks_llm
from models.schemas import Incident, Message, ProcessedMessage
from services.llm_client import LLMClient


class IncidentRouter:
    """Route incoming semantic messages into an evolving incident store."""

    TIME_WINDOW_S = 600

    def __init__(self, incident_store: IncidentStore, llm: Optional[LLMClient] = None) -> None:
        self.store = incident_store
        self.llm = llm
        self.incidents: dict[str, Incident] = {
            inc.incident_id: inc for inc in self.store.all_incidents()
        }

    def route_message(self, message: Message, processed: ProcessedMessage) -> Optional[Incident]:
        if processed.event_type == "noise":
            return None
        if processed.event_type == "resolution":
            return self._route_resolution(message, processed)
        return self._route_active_message(message, processed)

    def _route_active_message(self, message: Message, processed: ProcessedMessage) -> Incident:
        target = self._find_best_active_match(message, processed)
        if target is None:
            return self._create_incident(message, processed)
        return self._append_message(target, message, processed)

    def _find_best_active_match(self, message: Message, processed: ProcessedMessage) -> Optional[Incident]:
        candidates = [
            inc for inc in self.incidents.values()
            if inc.status == "active" and self._incident_channel(inc) == message.channel
        ]
        best: Optional[Incident] = None
        best_score = 0
        for candidate in candidates:
            score = self._match_score(candidate, message, processed)
            if score > best_score or (score == best_score and candidate.updated_at > (best.updated_at if best else 0)):
                best_score = score
                best = candidate
        if best_score >= 1:
            return best
        return None

    def _match_score(self, incident: Incident, message: Message, processed: ProcessedMessage) -> int:
        score = 0
        incident_entities = set(incident.entities or [])
        shared_entities = incident_entities.intersection(set(processed.entities or []))
        if shared_entities:
            score += 4
        if incident.incident_type == processed.topic:
            score += 3
        if self._message_within_window(incident, message):
            score += 1
        return score

    def _message_within_window(self, incident: Incident, message: Message) -> bool:
        return abs(message.timestamp - incident.updated_at) <= self.TIME_WINDOW_S

    def _incident_channel(self, incident: Incident) -> str:
        return incident.messages[0].channel if incident.messages else ""

    def _create_incident(self, message: Message, processed: ProcessedMessage) -> Incident:
        incident = Incident(
            incident_id=str(uuid.uuid4()),
            incident_type=processed.topic or "operational_event",
            severity=processed.urgency,
            summary=message.message.strip(),
            status="active",
            entities=sorted(set(processed.entities or [])),
            messages=[message],
            tasks=[],
            created_at=message.timestamp,
            updated_at=message.timestamp,
        )
        incident.summary = self._summarize_incident(incident)
        incident.tasks = self._generate_tasks(incident)
        self._persist_incident(incident)
        return incident

    def _append_message(self, incident: Incident, message: Message, processed: ProcessedMessage) -> Incident:
        severity = self._merge_severity(incident.severity, processed.urgency)
        entities = sorted(set(incident.entities or []) | set(processed.entities or []))
        updated = incident.model_copy(
            update={
                "severity": severity,
                "entities": entities,
                "messages": [*incident.messages, message],
                "updated_at": message.timestamp,
            }
        )
        updated.summary = self._summarize_incident(updated)
        updated.tasks = self._generate_tasks(updated)
        self._persist_incident(updated)
        return updated

    def _route_resolution(self, message: Message, processed: ProcessedMessage) -> Optional[Incident]:
        target = self._find_best_active_match(message, processed)
        if target is None:
            return None
        resolved = target.model_copy(
            update={
                "status": "resolved",
                "messages": [*target.messages, message],
                "updated_at": message.timestamp,
                "summary": append_resolution_note(target.summary, message),
            }
        )
        self._persist_incident(resolved)
        return resolved

    def _merge_severity(self, current: str, incoming: str) -> str:
        order = {"low": 1, "medium": 2, "high": 3}
        return incoming if order.get(incoming, 2) > order.get(current, 2) else current

    def _summarize_incident(self, incident: Incident) -> str:
        if self.llm is None:
            return incident.summary or "Operational incident reported."
        return generate_summary_llm(self.llm, incident)

    def _generate_tasks(self, incident: Incident) -> list[dict]:
        if incident.status != "active" or incident.severity not in ("medium", "high"):
            return []
        return generate_tasks_llm(
            self.llm,
            incident,
            incident.messages,
            incident.severity,
            "",
        )

    def _persist_incident(self, incident: Incident) -> None:
        if incident.incident_id in self.incidents:
            self.store.replace_incident(incident)
        else:
            self.store.append(incident)
        self.incidents[incident.incident_id] = incident
