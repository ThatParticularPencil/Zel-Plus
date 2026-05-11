from __future__ import annotations

from pathlib import Path

from engine.incident_router import IncidentRouter
from engine.memory import IncidentStore
from models.schemas import Incident, Message, ProcessedMessage


def test_warehouse_incident_sequence_routes_to_one_incident(tmp_path: Path) -> None:
    store = IncidentStore(tmp_path / "inc.json")
    router = IncidentRouter(store, llm=None)

    first = Message(
        channel="warehouse_1",
        timestamp=10,
        speaker="worker_1",
        message="forklift stopped near dock 2",
    )
    first_processed = ProcessedMessage(
        event_type="report",
        urgency="medium",
        topic="operational_obstruction",
        entities=["forklift", "dock 2"],
    )
    incident = router.route_message(first, first_processed)
    assert incident is not None
    assert incident.status == "active"
    assert incident.severity == "medium"
    assert incident.incident_type == "operational_obstruction"
    assert len(incident.messages) == 1
    incident_id = incident.incident_id

    second = Message(
        channel="warehouse_1",
        timestamp=40,
        speaker="worker_2",
        message="loading lane is getting blocked at dock 2",
    )
    second_processed = ProcessedMessage(
        event_type="update",
        urgency="medium",
        topic="operational_obstruction",
        entities=["dock 2", "loading lane"],
    )
    incident = router.route_message(second, second_processed)
    assert incident is not None
    assert incident.incident_id == incident_id
    assert incident.severity == "medium"
    assert len(incident.messages) == 2
    assert incident.status == "active"

    noise = Message(
        channel="warehouse_1",
        timestamp=60,
        speaker="worker_3",
        message="did anyone take my scanner charger again",
    )
    noise_processed = ProcessedMessage(
        event_type="noise",
        urgency="low",
        topic="misc_request",
        entities=["scanner charger"],
    )
    assert router.route_message(noise, noise_processed) is None
    assert len(router.incidents[incident.incident_id].messages) == 2

    fourth = Message(
        channel="warehouse_1",
        timestamp=80,
        speaker="worker_4",
        message="all pallet movement near dock 2 has stopped",
    )
    fourth_processed = ProcessedMessage(
        event_type="update",
        urgency="high",
        topic="operational_obstruction",
        entities=["dock 2", "pallet movement"],
    )
    incident = router.route_message(fourth, fourth_processed)
    assert incident is not None
    assert incident.severity == "high"
    assert len(incident.messages) == 3

    fifth = Message(
        channel="warehouse_1",
        timestamp=100,
        speaker="worker_5",
        message="possible hydraulic leak under the forklift",
    )
    fifth_processed = ProcessedMessage(
        event_type="report",
        urgency="high",
        topic="equipment_malfunction",
        entities=["forklift", "hydraulic leak"],
    )
    incident = router.route_message(fifth, fifth_processed)
    assert incident is not None
    assert incident.incident_type == "equipment_malfunction"
    assert incident.severity == "high"
    assert incident.tasks != []

    seventh = Message(
        channel="warehouse_1",
        timestamp=120,
        speaker="worker_6",
        message="maintenance team dispatched to dock 2",
    )
    seventh_processed = ProcessedMessage(
        event_type="update",
        urgency="high",
        topic="equipment_malfunction",
        entities=["maintenance team", "dock 2"],
    )
    incident = router.route_message(seventh, seventh_processed)
    assert incident is not None
    assert incident.status == "in_progress"

    eighth = Message(
        channel="warehouse_1",
        timestamp=140,
        speaker="worker_7",
        message="hydraulic leak contained and loading lane reopened",
    )
    eighth_processed = ProcessedMessage(
        event_type="resolution",
        urgency="high",
        topic="equipment_malfunction",
        entities=["hydraulic leak", "loading lane"],
    )
    incident = router.route_message(eighth, eighth_processed)
    assert incident is not None
    assert incident.status == "resolved"
    assert len(incident.messages) == 6

    ninth = Message(
        channel="warehouse_1",
        timestamp=160,
        speaker="worker_8",
        message="dock 2 forklift issue resolved now",
    )
    ninth_processed = ProcessedMessage(
        event_type="resolution",
        urgency="high",
        topic="equipment_malfunction",
        entities=["dock 2", "forklift"],
    )
    incident = router.route_message(ninth, ninth_processed)
    assert incident is not None
    assert incident.status == "resolved"
    assert len(incident.messages) == 7
