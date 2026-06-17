# lacuna/taxonomy/crosswalk.py
"""Crosswalk matching: map a source label (e.g. a Google Books category, which is
BISAC-derived) to a canonical BISAC code by embedding cosine similarity, then decide
accept/reject/queue (PRD §9, §13). Decision logic is pure; the embedding + DB
persistence in learn_crosswalk() is integration-deferred."""
from __future__ import annotations

from enum import Enum


class MatchDecision(str, Enum):
    ACCEPT = "accept"
    REJECT = "reject"
    QUEUE = "queue"


def classify_match(similarity: float, *, accept: float, reject: float) -> MatchDecision:
    if similarity >= accept:
        return MatchDecision.ACCEPT
    if similarity < reject:
        return MatchDecision.REJECT
    return MatchDecision.QUEUE


def best_match(similarities: dict[str, float]) -> tuple[str | None, float]:
    """Return (bisac_code, similarity) of the best candidate, or (None, 0.0)."""
    if not similarities:
        return (None, 0.0)
    code = max(similarities, key=similarities.get)
    return (code, similarities[code])


def learn_crosswalk(source: str, source_label: str):  # pragma: no cover
    """Integration entrypoint (deferred): embed source_label with all-MiniLM-L6-v2,
    cosine-compare to canonical BISAC labels, classify, and persist to
    taxonomy_crosswalk (accept/reject) or unmapped_labels (queue). Requires models +
    Supabase."""
    raise NotImplementedError(
        "learn_crosswalk requires pinned models and Supabase; decision logic is in "
        "classify_match/best_match and is unit-tested.")
