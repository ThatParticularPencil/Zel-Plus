from __future__ import annotations

import os
import re
import uuid

import numpy as np

from engine.message_ingestor import BufferedMessage
from models.schemas import ClusterMeta
from services.embedding_client import EmbeddingClient


TIME_WINDOW_S = int(os.getenv("IIE_CLUSTER_TIME_WINDOW_S", "300"))
SIM_THRESHOLD = float(os.getenv("IIE_EMBED_CLUSTER_THRESHOLD", "0.62"))

_GENERIC_TOPICS = frozenset(
    {
        "",
        "general",
        "frontline_message",
        "unclassified",
        "operational_event",
    }
)

# Shared operational nouns — one match + same channel/window links related chatter
_ANCHOR_TOKENS = frozenset(
    {
        "cabinet",
        "door",
        "aisle",
        "shelf",
        "lock",
        "dock",
        "forklift",
        "spill",
        "customer",
        "register",
        "checkout",
        "cooler",
        "freezer",
        "bathroom",
        "leak",
        "power",
    }
)


def _tokens(msg: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", msg.lower()) if len(w) >= 3}


def _lexical_or_anchor_link(text_a: str, text_b: str) -> bool:
    ta, tb = _tokens(text_a), _tokens(text_b)
    if not ta or not tb:
        return False
    shared = ta & tb
    if len(shared) >= 2:
        return True
    if shared & _ANCHOR_TOKENS:
        return True
    # single strong overlap on short utterances
    if len(shared) == 1 and max(len(ta), len(tb)) <= 8:
        return True
    return False


def _generic_topic(topic: str) -> bool:
    t = topic.strip().lower()
    return t in _GENERIC_TOPICS


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
    """Rule-based clustering: same channel, time window, topic match or embedding or lexical anchor."""
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
            shared_topic = bool(ti and tj and ti == tj and not (_generic_topic(ti) and _generic_topic(tj)))
            sim = _cosine_sim(vecs[i], vecs[j])
            msg_i = active[i].message.message
            msg_j = active[j].message.message
            lexical = _lexical_or_anchor_link(msg_i, msg_j)
            if shared_topic or sim > SIM_THRESHOLD or lexical:
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
