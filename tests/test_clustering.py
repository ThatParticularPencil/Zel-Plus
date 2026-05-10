from __future__ import annotations

from engine.clustering import TIME_WINDOW_S, cluster_messages
from engine.message_ingestor import BufferedMessage
from models.schemas import Message, ProcessedMessage
from services.embedding_client import EmbeddingClient


def _buf(
    internal_id: str,
    channel: str,
    ts: int,
    text: str,
    *,
    topic: str = "same_topic",
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
            intent=intent,
            urgency="medium",
            topic=topic,
            entities=[],
        ),
    )


def test_cluster_merges_same_topic_within_window() -> None:
    embedder = EmbeddingClient()
    a = _buf("a", "ch", 100, "one", topic="stock_issue")
    b = _buf("b", "ch", 150, "two", topic="stock_issue")
    clusters = cluster_messages([a, b], embedder)
    assert len(clusters) == 1
    assert set(clusters[0].message_ids) == {"a", "b"}


def test_cluster_skips_noise() -> None:
    embedder = EmbeddingClient()
    a = _buf("a", "ch", 100, "one", topic="t", intent="noise")
    b = _buf("b", "ch", 110, "two", topic="t")
    clusters = cluster_messages([a, b], embedder)
    assert len(clusters) == 1
    assert clusters[0].message_ids == ["b"]


def test_cluster_splits_across_time_window() -> None:
    embedder = EmbeddingClient()
    a = _buf("a", "ch", 0, "one", topic="t")
    b = _buf("b", "ch", TIME_WINDOW_S + 10, "two", topic="t")
    clusters = cluster_messages([a, b], embedder)
    assert len(clusters) == 2


def test_cluster_splits_different_topics_no_embedding_link() -> None:
    """Different topics and dissimilar text → two components (hash embed is topic-heavy)."""
    embedder = EmbeddingClient()
    a = _buf("a", "ch", 100, "aaaaaaa", topic="alpha_unique_xyz")
    b = _buf("b", "ch", 110, "bbbbbbb", topic="beta_unique_zzz")
    clusters = cluster_messages([a, b], embedder)
    assert len(clusters) == 2
