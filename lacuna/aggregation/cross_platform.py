# lacuna/aggregation/cross_platform.py
"""Cross-platform fusion (PRD §9). Per-platform normalization FIRST, then merge
aspect clusters by label-embedding similarity. Local-only; no external LLM."""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

import numpy as np


def normalize_ratings_per_platform(ratings: dict[str, list[float]]) -> dict[str, list[float]]:
    """z-score within each platform (own rating culture). Zero-variance → all 0.0."""
    out: dict[str, list[float]] = {}
    for platform, vals in ratings.items():
        arr = np.asarray(vals, dtype=float)
        std = arr.std()
        out[platform] = list((arr - arr.mean()) / std) if std > 0 else [0.0] * len(arr)
    return out


@dataclass
class AspectClusterIn:
    label: str
    platform: str
    reviewer_count: int
    helpful_weight: float
    member_count: int


@dataclass
class MergedCluster:
    label: str
    platforms: tuple[str, ...]
    reviewer_count: int
    helpful_weight: float
    member_count: int
    cross_platform: bool = field(default=False)


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    return float(a @ b / (na * nb)) if na and nb else 0.0


def merge_clusters(clusters: Sequence[AspectClusterIn],
                   *, embedder: Callable[[Sequence[str]], np.ndarray],
                   threshold: float) -> list[MergedCluster]:
    """Union-find merge of clusters whose label embeddings have cosine >= threshold."""
    n = len(clusters)
    if n == 0:
        return []
    vecs = np.asarray(embedder([c.label for c in clusters]))
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        parent[find(a)] = find(b)

    for i in range(n):
        for j in range(i + 1, n):
            if _cosine(vecs[i], vecs[j]) >= threshold:
                union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)

    out: list[MergedCluster] = []
    for members in groups.values():
        cs = [clusters[i] for i in members]
        platforms = tuple(sorted({c.platform for c in cs}))
        rep = max(cs, key=lambda c: c.reviewer_count)  # most-supported label as representative
        out.append(MergedCluster(
            label=rep.label, platforms=platforms,
            reviewer_count=sum(c.reviewer_count for c in cs),
            helpful_weight=sum(c.helpful_weight for c in cs),
            member_count=sum(c.member_count for c in cs),
            cross_platform=len(platforms) > 1,
        ))
    return out


def agreement_pct(clusters: Sequence["MergedCluster"], *, top_n: int) -> float:
    """Share of a candidate's top-N complaints (by reviewer_count) confirmed on >1 platform."""
    if not clusters:
        return 0.0
    top = sorted(clusters, key=lambda c: c.reviewer_count, reverse=True)[:top_n]
    return sum(1 for c in top if c.cross_platform) / len(top)
