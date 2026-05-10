from __future__ import annotations

import math
import uuid
from typing import Optional

from engine.memory import IncidentStore
from engine.resolution_routing import append_resolution_note
from engine.summarizer import generate_summary_llm
from engine.task_generator import generate_tasks_llm
from models.schemas import Incident, Message, ProcessedMessage
from services.embedding_client import EmbeddingClient
from services.llm_client import LLMClient


class IncidentRouter:
    """Route incoming semantic messages into an evolving incident store."""

    TIME_WINDOW_S = 600
    MATCH_EMBEDDING_THRESHOLD = 0.70
    ATTACH_THRESHOLD = 0.75
    SOFT_ATTACH_THRESHOLD = 0.45
    ENTITY_WEIGHT = 0.45
    TIME_WEIGHT = 0.25
    EMBEDDING_WEIGHT = 0.20
    URGENCY_WEIGHT = 0.10

    def __init__(
        self,
        incident_store: IncidentStore,
        llm: Optional[LLMClient] = None,
        embedder: Optional[EmbeddingClient] = None,
    ) -> None:
        self.store = incident_store
        self.llm = llm
        self.embedder = embedder
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
        candidates = self._build_candidates(message, processed, {"active", "in_progress"})
        best: Optional[Incident] = None
        best_score = 0.0
        for candidate in candidates:
            score = self._match_score(candidate, message, processed)
            if score > best_score or (score == best_score and candidate.updated_at > (best.updated_at if best else 0)):
                best_score = score
                best = candidate
        if best is None:
            return None
        if best.incident_type == processed.topic and self._message_within_window(best, message):
            return best
        if best_score >= self.ATTACH_THRESHOLD:
            return best
        if best_score >= self.SOFT_ATTACH_THRESHOLD and self._has_strong_hard_signal(best, message, processed):
            return best
        return None

    def _find_best_resolution_match(self, message: Message, processed: ProcessedMessage) -> Optional[Incident]:
        candidates = self._build_candidates(message, processed, {"active", "in_progress", "resolved"})
        best: Optional[Incident] = None
        best_score = 0.0
        for candidate in candidates:
            score = self._match_score(candidate, message, processed)
            if score > best_score or (score == best_score and candidate.updated_at > (best.updated_at if best else 0)):
                best_score = score
                best = candidate
        if best is None:
            return None
        if (
            best.incident_type == processed.topic
            or self._topic_overlap(best.incident_type, processed.topic)
        ) and self._message_within_window(best, message):
            return best
        if best_score >= self.SOFT_ATTACH_THRESHOLD:
            return best
        return None

    def _build_candidates(
        self,
        message: Message,
        processed: ProcessedMessage,
        statuses: set[str],
    ) -> list[Incident]:
        message_entities = set(processed.entities or [])
        candidates: list[Incident] = []
        for incident in self.incidents.values():
            if incident.status not in statuses:
                continue
            if self._incident_channel(incident) != message.channel:
                if processed.urgency != "high":
                    continue
            if not self._is_candidate(incident, message, processed, message_entities):
                continue
            candidates.append(incident)
        return candidates

    def _is_candidate(
        self,
        incident: Incident,
        message: Message,
        processed: ProcessedMessage,
        message_entities: set[str],
    ) -> bool:
        incident_entities = set(incident.entities or [])
        shared_entities = incident_entities.intersection(message_entities)
        same_topic = incident.incident_type == processed.topic
        recent = self._message_within_window(incident, message)

        if same_topic:
            return recent or bool(shared_entities)
        if shared_entities and recent:
            return True
        if processed.event_type == "resolution" and self._topic_overlap(incident.incident_type, processed.topic):
            return recent
        if self.embedder is None:
            return False
        return self._embedding_similarity(message, incident) >= self.MATCH_EMBEDDING_THRESHOLD

    def _match_score(self, incident: Incident, message: Message, processed: ProcessedMessage) -> float:
        incident_entities = set(incident.entities or [])
        processed_entities = set(processed.entities or [])
        shared_entities = incident_entities.intersection(processed_entities)
        denominator = max(min(len(incident_entities), len(processed_entities)), 1)
        entity_score = len(shared_entities) / denominator
        time_score = self._time_proximity_score(incident, message)
        embedding_score = self._embedding_similarity(message, incident)
        urgency_score = 1.0 if incident.severity == processed.urgency else 0.0
        topic_bonus = 0.1 if incident.incident_type == processed.topic else 0.0

        score = (
            self.ENTITY_WEIGHT * entity_score
            + self.TIME_WEIGHT * time_score
            + self.EMBEDDING_WEIGHT * embedding_score
            + self.URGENCY_WEIGHT * urgency_score
            + topic_bonus
        )
        return min(score, 1.0)

    def _time_proximity_score(self, incident: Incident, message: Message) -> float:
        delta = abs(message.timestamp - incident.updated_at)
        return math.exp(-delta / self.TIME_WINDOW_S) if delta >= 0 else 0.0

    def _embedding_similarity(self, message: Message, incident: Incident) -> float:
        if self.embedder is None:
            return 0.0
        message_vector = self.embedder.embed([message.message.strip()])[0]
        incident_vector = self.embedder.embed([incident.summary or incident.incident_type])[0]
        dot = sum(a * b for a, b in zip(message_vector, incident_vector))
        mag_a = math.sqrt(sum(a * a for a in message_vector))
        mag_b = math.sqrt(sum(b * b for b in incident_vector))
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return max(min(dot / (mag_a * mag_b), 1.0), -1.0)

    def _has_strong_hard_signal(self, incident: Incident, message: Message, processed: ProcessedMessage) -> bool:
        incident_entities = set(incident.entities or [])
        shared_entities = incident_entities.intersection(set(processed.entities or []))
        if incident.incident_type == processed.topic:
            return True
        if shared_entities and self._message_within_window(incident, message):
            return True
        if self.embedder is None:
            return False
        return self._embedding_similarity(message, incident) >= self.MATCH_EMBEDDING_THRESHOLD

    def _message_within_window(self, incident: Incident, message: Message) -> bool:
        return abs(message.timestamp - incident.updated_at) <= self.TIME_WINDOW_S

    def _topic_overlap(self, incident_type: str, topic: str) -> bool:
        incident_norm = (incident_type or "").lower().replace("_", " ").strip()
        topic_norm = (topic or "").lower().replace("_", " ").strip()
        if not incident_norm or not topic_norm:
            return False
        if topic_norm in incident_norm or incident_norm in topic_norm:
            return True
        incident_tokens = set(incident_norm.split())
        topic_tokens = set(topic_norm.split())
        return bool(incident_tokens.intersection(topic_tokens))

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
        status = incident.status
        if processed.event_type == "update" and status == "active" and self._is_progress_update(message.message):
            status = "in_progress"
        incident_type = processed.topic if processed.topic and processed.topic != incident.incident_type else incident.incident_type
        entities = sorted(set(incident.entities or []) | set(processed.entities or []))
        updated = incident.model_copy(
            update={
                "incident_type": incident_type,
                "severity": severity,
                "status": status,
                "entities": entities,
                "messages": [*incident.messages, message],
                "updated_at": message.timestamp,
            }
        )
        updated.summary = self._summarize_incident(updated)
        updated.tasks = self._generate_tasks(updated)
        self._persist_incident(updated)
        return updated

    def _is_progress_update(self, text: str) -> bool:
        normalized = text.lower()
        progress_signals = (
            "dispatch",
            "dispatched",
            "maintenance",
            "team",
            "crew",
            "assigned",
            "en route",
            "on site",
            "responding",
            "response",
        )
        return any(signal in normalized for signal in progress_signals)

    def _route_resolution(self, message: Message, processed: ProcessedMessage) -> Optional[Incident]:
        target = self._find_best_resolution_match(message, processed)
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
