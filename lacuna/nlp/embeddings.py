# lacuna/nlp/embeddings.py
"""Local embeddings with a per-text hash cache (PRD §7). Default encoder lazily
loads all-MiniLM-L6-v2 at the pinned revision; an encoder can be injected for tests.
Nothing leaves the machine."""
from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence

import numpy as np

EMBED_DIM = 384


def review_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_default_encoder() -> Callable[[Sequence[str]], np.ndarray]:  # pragma: no cover
    from lacuna.config import load_advanced
    from sentence_transformers import SentenceTransformer
    node = load_advanced()["models"]["embedding"]
    if node["revision"] in (None, "<resolved-at-build>"):
        raise RuntimeError("embedding model revision not pinned — run scripts/pin_revisions.py")
    model = SentenceTransformer(node["name"], revision=node["revision"], device="cpu")
    return lambda texts: np.asarray(
        model.encode(list(texts), normalize_embeddings=True, convert_to_numpy=True))


class Embedder:
    def __init__(self, encoder: Callable[[Sequence[str]], np.ndarray] | None = None):
        self._encoder = encoder
        self._cache: dict[str, np.ndarray] = {}

    @property
    def encoder(self) -> Callable[[Sequence[str]], np.ndarray]:
        if self._encoder is None:
            self._encoder = _load_default_encoder()
        return self._encoder

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        missing = [t for t in texts if review_hash(t) not in self._cache]
        # de-dup the missing list preserving order
        seen: set[str] = set()
        unique_missing = [t for t in missing if not (t in seen or seen.add(t))]
        if unique_missing:
            vecs = self.encoder(unique_missing)
            for t, v in zip(unique_missing, vecs):
                self._cache[review_hash(t)] = np.asarray(v)
        return np.array([self._cache[review_hash(t)] for t in texts])
