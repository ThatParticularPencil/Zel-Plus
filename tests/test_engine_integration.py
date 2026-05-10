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
    raw = {"channel": "store_1", "timestamp": 10, "speaker": "w1", "message": "issue at aisle 2"}
    r1 = eng.process_pipeline(raw)
    assert r1["processed"]["intent"] == "report"
    assert len(r1["incidents"]) == 0

    raw2 = {"channel": "store_1", "timestamp": 50, "speaker": "w2", "message": "still there"}
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
    for i, ts in enumerate([100, 150, 200], start=1):
        out = eng.process_pipeline({**base, "timestamp": ts, "message": f"m{i}"})
        assert len(out["incidents"]) == 0

    out4 = eng.process_pipeline({**base, "timestamp": 250, "message": "m4"})
    assert len(out4["incidents"]) == 1
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
    assert len(flushed["incidents"]) == 1
    assert len(flushed["incidents"][0]["incident"]["messages"]) == 1
