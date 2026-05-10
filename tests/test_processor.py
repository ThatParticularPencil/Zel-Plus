from __future__ import annotations

from models.schemas import Message
from engine.processor import _fallback_processed, process_message_llm


def test_fallback_empty_is_noise() -> None:
    m = Message(channel="c", timestamp=1, speaker="s", message=" ")
    p = _fallback_processed(m)
    assert p.intent == "noise"


def test_fallback_operational_is_report() -> None:
    m = Message(channel="c", timestamp=1, speaker="s", message="help at aisle 4")
    p = _fallback_processed(m)
    assert p.intent == "report"
    assert p.topic == "frontline_message"


def test_fallback_urgent_keyword() -> None:
    m = Message(channel="c", timestamp=1, speaker="s", message="urgent spill on floor")
    p = _fallback_processed(m)
    assert p.urgency == "high"


def test_process_message_llm_offline_uses_fallback() -> None:
    m = Message(channel="c", timestamp=1, speaker="s", message="status update")
    p = process_message_llm(None, m)
    assert p.intent == "report"
    assert p.urgency == "medium"
