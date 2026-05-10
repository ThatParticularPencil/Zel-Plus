from __future__ import annotations

import uuid

import numpy as np

from engine.message_ingestor import BufferedMessage
from models.schemas import ClusterMeta
from services.embedding_client import EmbeddingClient


TIME_WINDOW_S = 300
SIM_THRESHOLD = 0.75


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def cluster_messages(
    channel_messages: list[BufferedMessage],
    embedder: EmbeddingClient,
) -> list[ClusterMeta]:
    """Rule-based clustering: same channel, time window, topic match or embedding sim."""
    active: list[BufferedMessage] = []
    for b in channel_messages:
        if b.processed is None:
            continue
        if b.processed.intent == "noise":
            continue
        active.append(b)
    if not active:
        return []

    texts = [f"{b.processed.topic} | {b.message.message}" for b in active]
    vecs = embedder.embed(texts)

    n = len(active)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[rj] = ri

    for i in range(n):
        for j in range(i + 1, n):
            dt = abs(active[i].message.timestamp - active[j].message.timestamp)
            if dt >= TIME_WINDOW_S:
                continue
            ti = active[i].processed.topic.strip().lower() if active[i].processed else ""
            tj = active[j].processed.topic.strip().lower() if active[j].processed else ""
            shared_topic = bool(ti and tj and ti == tj)
            sim = _cosine_sim(vecs[i], vecs[j])
            if shared_topic or sim > SIM_THRESHOLD:
                union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(n):
        r = find(i)
        groups.setdefault(r, []).append(i)

    clusters: list[ClusterMeta] = []
    for idxs in groups.values():
        cid = f"inc_{uuid.uuid4().hex[:8]}"
        ids = [active[i].internal_id for i in sorted(idxs)]
        clusters.append(ClusterMeta(incident_id=cid, message_ids=ids))
    return clusters
