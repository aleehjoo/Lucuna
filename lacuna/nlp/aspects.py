# lacuna/nlp/aspects.py
"""Local zero-shot aspect labeling (PRD §7). Default classifier lazily loads
bart-large-mnli at the pinned revision; injectable for tests. Produces a PARAPHRASED
label + representative summary — never a raw review quote."""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

ASPECT_TAXONOMY = [
    "outdated", "too_basic", "too_advanced", "poor_examples",
    "inaccurate", "badly_structured", "overpriced", "repetitive",
]

# Paraphrase templates keyed by aspect — keeps exports quote-free (ToU + token economy).
_PARAPHRASE = {
    "outdated": "Readers say the material feels outdated.",
    "too_basic": "Readers find the content too basic.",
    "too_advanced": "Readers find the content too advanced.",
    "poor_examples": "Readers criticize the quality of examples.",
    "inaccurate": "Readers report inaccuracies.",
    "badly_structured": "Readers find the structure confusing.",
    "overpriced": "Readers feel it is overpriced.",
    "repetitive": "Readers find the content repetitive.",
}


@dataclass
class AspectResult:
    label: str
    score: float
    representative: str


def pick_aspect(scores: dict[str, float]) -> tuple[str, float]:
    label = max(scores, key=scores.get)
    return label, scores[label]


def _load_default_classifier() -> Callable[[str, Sequence[str]], dict[str, float]]:  # pragma: no cover
    from lacuna.config import load_advanced
    from transformers import pipeline
    node = load_advanced()["models"]["zero_shot"]
    if node["revision"] in (None, "<resolved-at-build>"):
        raise RuntimeError("zero_shot model revision not pinned — run scripts/pin_revisions.py")
    clf = pipeline("zero-shot-classification", model=node["name"],
                   revision=node["revision"], device=-1)

    def _classify(text: str, candidate_labels: Sequence[str]) -> dict[str, float]:
        out = clf(text, candidate_labels=list(candidate_labels), multi_label=True)
        return dict(zip(out["labels"], out["scores"]))

    return _classify


class AspectLabeler:
    def __init__(self, classifier: Callable[[str, Sequence[str]], dict[str, float]] | None = None):
        self._classifier = classifier

    @property
    def classifier(self) -> Callable[[str, Sequence[str]], dict[str, float]]:
        if self._classifier is None:
            self._classifier = _load_default_classifier()
        return self._classifier

    def label_cluster(self, texts: Sequence[str], candidate_labels: Sequence[str] | None = None) -> AspectResult:
        labels = list(candidate_labels or ASPECT_TAXONOMY)
        # Use the longest member text as the cluster representative seed (most content).
        seed = max(texts, key=len) if texts else ""
        scores = self.classifier(seed, labels)
        label, score = pick_aspect(scores)
        return AspectResult(label=label, score=float(score),
                            representative=_PARAPHRASE.get(label, f"Readers raise: {label}."))
