from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def offline_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IIE_OFFLINE", "1")
    monkeypatch.setenv("IIE_EMIT_MIN_MESSAGES", "2")
    monkeypatch.setenv("IIE_AUTO_RESOLVE", "false")


def test_pipeline_two_messages_one_incident(
    tmp_path: Path,
    offline_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("IIE_STORAGE_DIR", str(tmp_path))
    from app.main import IncidentEngine

    eng = IncidentEngine(storage_dir=tmp_path, auto_resolve=False)
    raw = {"channel": "store_1", "timestamp": 10, "speaker": "w1", "message": "customer waiting at register 3"}
    r1 = eng.process_pipeline(raw)
    assert r1["processed"]["event_type"] == "report"
    assert len(r1["incidents"]) == 1

    raw2 = {"channel": "store_1", "timestamp": 50, "speaker": "w2", "message": "still backed up at register 3"}
    r2 = eng.process_pipeline(raw2)
    assert len(r2["incidents"]) == 1
    inc = r2["incidents"][0]["incident"]
    assert len(inc["messages"]) == 2
    assert inc["messages"][0]["speaker"] == "w1"
    assert len(inc["tasks"]) >= 1


def test_emit_min_four_requires_four_messages(
    tmp_path: Path,
    offline_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("IIE_EMIT_MIN_MESSAGES", "4")
    monkeypatch.setenv("IIE_STORAGE_DIR", str(tmp_path))
    from app.main import IncidentEngine

    eng = IncidentEngine(storage_dir=tmp_path, auto_resolve=False)
    base = {"channel": "s", "speaker": "w", "message": "x"}
    existing_incident_id = None
    for i, ts in enumerate([100, 150, 200], start=1):
        out = eng.process_pipeline(
            {
                **base,
                "timestamp": ts,
                "message": f"freezer alarm on aisle 5 case {i} still acting up",
            }
        )
        assert len(out["incidents"]) == 1
        if existing_incident_id is None:
            existing_incident_id = out["incidents"][0]["incident"]["incident_id"]
        assert out["incidents"][0]["incident"]["incident_id"] == existing_incident_id

    out4 = eng.process_pipeline(
        {
            **base,
            "timestamp": 250,
            "message": "freezer alarm aisle 5 now stable after reset",
        }
    )
    assert len(out4["incidents"]) == 1
    assert out4["incidents"][0]["incident"]["incident_id"] == existing_incident_id
    assert len(out4["incidents"][0]["incident"]["messages"]) == 4


def test_flush_eof_emits_singleton(
    tmp_path: Path,
    offline_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("IIE_EMIT_MIN_MESSAGES", "4")
    monkeypatch.setenv("IIE_STORAGE_DIR", str(tmp_path))
    from app.main import IncidentEngine

    eng = IncidentEngine(storage_dir=tmp_path, auto_resolve=False)
    eng.process_pipeline({"channel": "solo", "timestamp": 1, "speaker": "a", "message": "only message"})
    flushed = eng.flush_eof()
    assert len(flushed["incidents"]) == 0
