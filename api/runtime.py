# api/runtime.py
"""Warm-model singleton (Frontend PRD §2/§13.4). The ~1.6GB zero-shot model and the
embedding model load ONCE here at backend startup and stay in memory; live search
reuses them and never reloads. Tests inject fakes via `for_testing` so no model is
downloaded. Nothing here sends text off the machine (CLAUDE.md §3)."""
from __future__ import annotations

from dataclasses import dataclass

from lacuna.nlp.aspects import AspectLabeler
from lacuna.nlp.embeddings import Embedder


@dataclass
class EngineRuntime:
    embedder: Embedder
    labeler: AspectLabeler

    @classmethod
    def warm(cls) -> "EngineRuntime":
        """Construct and force model load. Surfaces the engine's 'revision not
        pinned' error loudly (CLAUDE.md §3) rather than masking it."""
        embedder = Embedder()
        labeler = AspectLabeler()
        _ = embedder.encoder      # triggers SentenceTransformer load (pinned revision)
        _ = labeler.classifier    # triggers bart-large-mnli load (pinned revision)
        return cls(embedder=embedder, labeler=labeler)

    @classmethod
    def for_testing(cls, *, embedder, labeler) -> "EngineRuntime":
        return cls(embedder=embedder, labeler=labeler)
