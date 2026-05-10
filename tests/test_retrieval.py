from __future__ import annotations

from engine.retrieval import format_rag_lines, retrieve_similar_memories
from models.schemas import MemoryEntry
from services.embedding_client import EmbeddingClient


def test_format_rag_lines_empty() -> None:
    assert format_rag_lines([]) == ""


def test_format_rag_lines_single() -> None:
    e = MemoryEntry(
        incident_type="retail_blockage",
        context_signature="sig",
        resolution="dispatch_log",
        outcome="success",
        timestamp=1,
    )
    text = format_rag_lines([e])
    assert "retail_blockage" in text
    assert "dispatch_log" in text


def test_retrieve_top_k_ordering() -> None:
    embedder = EmbeddingClient()
    memories = [
        MemoryEntry(
            incident_type="type_a",
            context_signature="sig1",
            resolution="r1",
            outcome="success",
            timestamp=1,
        ),
        MemoryEntry(
            incident_type="type_a",
            context_signature="sig1",
            resolution="r2",
            outcome="success",
            timestamp=2,
        ),
    ]
    out = retrieve_similar_memories(
        embedder,
        memories,
        incident_type="type_a",
        context_signature="sig1",
        top_k=1,
    )
    assert len(out) == 1
