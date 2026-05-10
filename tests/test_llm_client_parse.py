from __future__ import annotations

from services.llm_client import LLMClient


def test_parse_json_loose_plain_object() -> None:
    raw = '{"intent":"report","urgency":"low","topic":"t","entities":[]}'
    out = LLMClient._parse_json_loose(raw)
    assert out is not None
    assert out["intent"] == "report"


def test_parse_json_loose_strips_markdown_fence() -> None:
    raw = "```json\n{\"a\": 1}\n```"
    out = LLMClient._parse_json_loose(raw)
    assert out == {"a": 1}


def test_parse_json_loose_rejects_array() -> None:
    assert LLMClient._parse_json_loose("[1,2]") is None
