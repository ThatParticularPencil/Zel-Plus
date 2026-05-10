from __future__ import annotations

from engine.clustering import cluster_messages
from engine.message_ingestor import BufferedMessage
from models.schemas import Message, ProcessedMessage
from services.embedding_client import EmbeddingClient


def _buf(
    internal_id: str,
    channel: str,
    ts: int,
    text: str,
    *,
    topic: str = "frontline_message",
    intent: str = "report",
) -> BufferedMessage:
    return BufferedMessage(
        internal_id=internal_id,
        channel=channel,
        message=Message(
            channel=channel,
            timestamp=ts,
            speaker="w",
            message=text,
        ),
        processed=ProcessedMessage(
            event_type=intent,
            urgency="medium",
            topic=topic,
            entities=[],
        ),
    )


def test_generic_topic_still_merges_via_shared_anchor_words() -> None:
    """Same generic LLM topic but different wording — lexical/anchor link merges cluster."""
    embedder = EmbeddingClient()
    a = _buf("a", "ch", 100, "the locked cabinet still wont open in aisle 4", topic="frontline_message")
    b = _buf("b", "ch", 110, "hey i got the cabinet open now", topic="frontline_message")
    clusters = cluster_messages([a, b], embedder)
    assert len(clusters) == 1
    assert set(clusters[0].message_ids) == {"a", "b"}
