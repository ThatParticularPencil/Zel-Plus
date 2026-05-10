from __future__ import annotations

from pathlib import Path

from engine.memory import IncidentStore, MemoryStore
from models.schemas import Incident, MemoryEntry, Message


def test_memory_store_append_roundtrip(tmp_path: Path) -> None:
    p = tmp_path / "mem.json"
    store = MemoryStore(p)
    entry = MemoryEntry(
        incident_type="t",
        context_signature="c",
        resolution="dispatch",
        outcome="success",
        timestamp=42,
    )
    store.append(entry)
    all_e = store.all_entries()
    assert len(all_e) == 1
    assert all_e[0].resolution == "dispatch"


def test_incident_store_find_by_id(tmp_path: Path) -> None:
    p = tmp_path / "inc.json"
    store = IncidentStore(p)
    m = Message(channel="c", timestamp=1, speaker="s", message="x")
    inc = Incident(
        incident_id="inc_test_1",
        incident_type="t",
        severity="low",
        summary="s",
        status="active",
        messages=[m],
        tasks=[],
    )
    store.append(inc)
    found = store.find_by_id("inc_test_1")
    assert found is not None
    assert found["incident_id"] == "inc_test_1"

    store.update_last_status("inc_test_1", "resolved")
    found2 = store.find_by_id("inc_test_1")
    assert found2 is not None
    assert found2["status"] == "resolved"
