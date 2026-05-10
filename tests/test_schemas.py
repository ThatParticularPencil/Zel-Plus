from __future__ import annotations

import pytest
from pydantic import ValidationError

from models.schemas import Message, ProcessedMessage


def test_message_valid_minimal() -> None:
    m = Message(
        channel="c1",
        timestamp=1,
        speaker="s1",
        message="hello",
    )
    assert m.channel == "c1"


def test_message_rejects_missing_field() -> None:
    with pytest.raises(ValidationError):
        Message.model_validate({"channel": "c", "timestamp": 1, "speaker": "s"})


def test_processed_message_roundtrip() -> None:
    p = ProcessedMessage(
        intent="report",
        urgency="high",
        topic="test_topic",
        entities=["aisle_4"],
    )
    d = p.model_dump()
    assert ProcessedMessage.model_validate(d).topic == "test_topic"
