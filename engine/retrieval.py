from __future__ import annotations

import numpy as np

from models.schemas import MemoryEntry
from services.embedding_client import EmbeddingClient


def format_rag_lines(entries: list[MemoryEntry]) -> str:
    """Human-readable block for LLM prompts."""
    if not entries:
        return ""
    lines = ["Similar past incidents:"]
    for e in entries:
        lines.append(f"- type: {e.incident_type} → resolved via {e.resolution}")
    return "\n".join(lines)


def retrieve_similar_memories(
    embedder: EmbeddingClient,
    memories: list[MemoryEntry],
    *,
    incident_type: str,
    context_signature: str,
    top_k: int = 3,
) -> list[MemoryEntry]:
    if not memories:
        return []
    query = f"{incident_type}\n{context_signature}"
    q = embedder.embed([query])[0]

    def score(e: MemoryEntry) -> float:
        doc = f"{e.incident_type}\n{e.context_signature}\n{e.resolution}"
        v = embedder.embed([doc])[0]
        na = np.linalg.norm(q)
        nb = np.linalg.norm(v)
        if na == 0 or nb == 0:
            return 0.0
        return float(np.dot(q, v) / (na * nb))

    ranked = sorted(memories, key=score, reverse=True)
    return ranked[:top_k]
