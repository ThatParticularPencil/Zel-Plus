from __future__ import annotations

from fastapi.testclient import TestClient


def test_dashboard_state_shape() -> None:
    from app.main import create_app

    client = TestClient(create_app())
    r = client.get("/dashboard/state")
    assert r.status_code == 200
    data = r.json()
    assert data["messages"] == []
    assert data["semantic"] == []
    assert data["incidents"] == []
    assert data["cluster_preview"] == []
    assert data["emit_jobs_pending"] == 0


def test_ingest_then_dashboard_feed() -> None:
    from app.main import create_app

    client = TestClient(create_app())
    client.post(
        "/ingest",
        json={
            "channel": "c",
            "timestamp": 10,
            "speaker": "w",
            "message": "hello world",
        },
    )
    r = client.get("/dashboard/state")
    assert r.status_code == 200
    msgs = r.json()["messages"]
    assert len(msgs) == 1
    assert msgs[0]["speaker"] == "w"
    assert msgs[0]["urgency"] in ("low", "medium", "high")
