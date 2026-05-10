from __future__ import annotations

import hashlib
import os
import re
from typing import Optional, Sequence

import numpy as np


def _l2_normalize(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    if n == 0:
        return v
    return v / n


class EmbeddingClient:
    """SentenceTransformers when available; token-overlap fallback otherwise."""

    def __init__(self, model_name: Optional[str] = None) -> None:
        self.model_name = model_name or os.getenv("IIE_EMBED_MODEL", "all-MiniLM-L6-v2")
        self._model = None
        self._dim: Optional[int] = None

    def _load_model(self):
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
            self._dim = int(self._model.get_sentence_embedding_dimension())
        except Exception:
            self._model = None
            self._dim = 256

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        self._load_model()
        if self._model is not None:
            return np.array(self._model.encode(list(texts), convert_to_numpy=True, show_progress_bar=False))
        return np.stack([self._hash_embed(t) for t in texts], axis=0)

    def similarity(self, a: str, b: str) -> float:
        ea = self.embed([a])[0]
        eb = self.embed([b])[0]
        return float(np.dot(_l2_normalize(ea), _l2_normalize(eb)))

    def _hash_embed(self, text: str) -> np.ndarray:
        """Deterministic bag-of-tokens embedding for clustering MVP."""
        dim = self._dim or 256
        vec = np.zeros(dim, dtype=np.float64)
        toks = re.findall(r"[a-z0-9]+", text.lower())
        if not toks:
            return vec
        for t in toks:
            h = hashlib.sha256(t.encode()).digest()
            idx = int.from_bytes(h[:4], "big") % dim
            vec[idx] += 1.0 + 0.01 * len(t)
        return _l2_normalize(vec)
