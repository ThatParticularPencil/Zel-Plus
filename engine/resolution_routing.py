"""Heuristics to attach resolution-style messages to open incidents."""

from __future__ import annotations

from models.schemas import Message, ProcessedMessage

# Phrases suggesting the issue is cleared or progress is complete (lowercase match)
_RESOLVED_PHRASES = (
    "resolved",
    "fixed it",
    "all fixed",
    "all clear",
    "got it open",
    "cabinet open",
    "open now",
    "got it working",
    "working now",
    "working again",
    "no longer",
    "not an issue",
    "issue cleared",
    "problem solved",
    "taken care of",
    "sorted out",
    "good now",
    "back to normal",
    "opened now",
    "its open",
    "it's open",
    "is open now",
    "opened the",
    "successfully opened",
)


def is_likely_resolution_message(text: str) -> bool:
    t = text.lower().strip()
    if len(t) < 4:
        return False
    return any(p in t for p in _RESOLVED_PHRASES)


def should_attempt_resolution_routing(processed: ProcessedMessage, message: str) -> bool:
    if processed.intent == "noise":
        return False
    if processed.intent == "update":
        return is_likely_resolution_message(message)
    if processed.intent in ("report", "none"):
        return is_likely_resolution_message(message)
    return False


def append_resolution_note(summary: str, m: Message) -> str:
    tail = f" [Resolved in field: {m.speaker} @ t={m.timestamp}: {m.message[:120]}]"
    if len(summary) + len(tail) > 1800:
        return summary[:1600] + "…" + tail
    return summary + tail
