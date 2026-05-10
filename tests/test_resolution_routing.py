from __future__ import annotations

from pathlib import Path

from engine.resolution_routing import is_likely_resolution_message, should_attempt_resolution_routing
from models.schemas import Incident, Message, ProcessedMessage, Task


def test_is_likely_resolution_message() -> None:
    assert is_likely_resolution_message("hey i got the cabinet open now")
    assert not is_likely_resolution_message("the cabinet still wont open")


def test_should_attempt_with_report_intent_if_text_resolves() -> None:
    p = ProcessedMessage(intent="report", urgency="medium", topic="t", entities=[])
    assert should_attempt_resolution_routing(p, "got it open now")


def test_resolution_closes_active_incident(tmp_path: Path) -> None:
    from app.main import IncidentEngine

    eng = IncidentEngine(storage_dir=tmp_path, auto_resolve=False)
    m0 = Message(channel="retail_store_4", timestamp=1, speaker="w1", message="cabinet stuck")
    inc = Incident(
        incident_id="inc_test_active",
        incident_type="cabinet_issue",
        severity="medium",
        summary="Cabinet stuck",
        status="active",
        messages=[m0],
        tasks=[Task(action="dispatch", priority="medium", parameters={}).model_dump()],
    )
    eng.incident_store.append(inc)

    buf = eng.ingest_message(
        {
            "channel": "retail_store_4",
            "timestamp": 99,
            "speaker": "w2",
            "message": "cabinet is open now, all good",
        }
    )
    proc = ProcessedMessage(intent="update", urgency="low", topic="cabinet", entities=[])
    out = eng._maybe_route_resolution(buf, proc, "retail_store_4")
    assert out is not None
    assert out.get("resolution_applied") == "inc_test_active"
    row = eng.incident_store.find_by_id("inc_test_active")
    assert row is not None
    assert row["status"] == "resolved"
    assert len(row["messages"]) == 2
