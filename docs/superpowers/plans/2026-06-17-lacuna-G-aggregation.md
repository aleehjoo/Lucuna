# Workstream G — Cross-Platform Aggregation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development / executing-plans. Steps use `- [ ]`.
>
> **⛔ GATE:** Per CLAUDE.md §4 / PRD §18, **do not author or run this code until G0 passes.** Ready, deferred.

**Goal:** Fuse the two sentiment-text platforms (Amazon corpus + Hardcover) into one aspect-cluster space (PRD §9): per-platform rating normalization **first**, then cross-platform cluster merge by aspect-label embedding similarity, then a cross-platform agreement metric that raises confidence.

**Architecture:** Pure cores + one injected embedder. `cross_platform.py`: `normalize_ratings_per_platform()` (z-score within platform — never blend rating cultures); `merge_clusters()` (union-find over aspect clusters whose **label embeddings** have cosine ≥ `cluster_merge_similarity`, reusing the local MiniLM embedder from D so nothing leaves the machine); `agreement_pct()` (share of a candidate's top complaints confirmed on >1 platform). The DB read/write wrapper is the only integration piece (deferred).

**Tech Stack:** numpy; the D `Embedder` (injectable). No external LLM (PRD §7).

**Depends on:** B, D, G0. **Blocks:** H, I.

> **Design notes (Sequential Thinking):** ordering is the silently-wrong trap — **normalize per platform before any blend**. Merge uses **cluster-label embeddings** (not raw review text, not a heavy pgvector self-join), keeping it local and cheap; centroid-of-members is unnecessary. `cluster_merge_similarity=0.75` is the approved threshold (distinct from the taxonomy `crosswalk_auto_accept`).

---

### Task G1: Per-platform rating normalization (`lacuna/aggregation/cross_platform.py`)

**Files:** Create `lacuna/aggregation/__init__.py` (empty), `lacuna/aggregation/cross_platform.py`; Test `tests/aggregation/__init__.py` (empty), `tests/aggregation/test_normalization.py`

- [ ] **Step 1: Failing test**

```python
# tests/aggregation/test_normalization.py
from lacuna.aggregation.cross_platform import normalize_ratings_per_platform

def test_zscore_within_platform_independently():
    data = {"amazon_corpus": [1.0, 3.0, 5.0], "hardcover": [4.0, 4.0, 4.0]}
    out = normalize_ratings_per_platform(data)
    # amazon spread -> mean 3 -> middle is 0.0
    assert abs(out["amazon_corpus"][1] - 0.0) < 1e-9
    assert out["amazon_corpus"][0] < 0 < out["amazon_corpus"][2]
    # hardcover zero variance -> all 0.0 (min-max fallback), never NaN
    assert out["hardcover"] == [0.0, 0.0, 0.0]
```

- [ ] **Step 2: Run → fail.** `python -m uv run pytest tests/aggregation/test_normalization.py -v`

- [ ] **Step 3: Implement (start the module)**

```python
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
```

- [ ] **Step 4: Run → pass.** **Step 5: Commit** `git commit -m "feat(G): per-platform rating normalization (z-score, zero-var safe)"`

---

### Task G2: Cluster merge by label embedding (`cross_platform.py` cont.)

**Files:** Modify `lacuna/aggregation/cross_platform.py`; Test `tests/aggregation/test_merge.py`

- [ ] **Step 1: Failing test** (inject a fake embedder)

```python
# tests/aggregation/test_merge.py
import numpy as np
from lacuna.aggregation.cross_platform import AspectClusterIn, merge_clusters

def _vec_embedder(label_to_vec):
    return lambda labels: np.array([label_to_vec[l] for l in labels])

def test_similar_labels_merge_across_platforms():
    clusters = [
        AspectClusterIn(label="outdated examples", platform="amazon_corpus", reviewer_count=10, helpful_weight=5.0, member_count=12),
        AspectClusterIn(label="examples are outdated", platform="hardcover", reviewer_count=4, helpful_weight=2.0, member_count=5),
        AspectClusterIn(label="too expensive", platform="amazon_corpus", reviewer_count=3, helpful_weight=1.0, member_count=3),
    ]
    emb = _vec_embedder({
        "outdated examples": [1.0, 0.0], "examples are outdated": [0.99, 0.01], "too expensive": [0.0, 1.0],
    })
    merged = merge_clusters(clusters, embedder=emb, threshold=0.75)
    # the two outdated clusters merge; the price one stays separate
    assert len(merged) == 2
    outdated = [m for m in merged if m.cross_platform][0]
    assert set(outdated.platforms) == {"amazon_corpus", "hardcover"}
    assert outdated.reviewer_count == 14 and outdated.member_count == 17

def test_single_platform_clusters_flagged_not_cross():
    clusters = [AspectClusterIn(label="repetitive", platform="amazon_corpus", reviewer_count=2, helpful_weight=1.0, member_count=2)]
    emb = _vec_embedder({"repetitive": [1.0, 0.0]})
    merged = merge_clusters(clusters, embedder=emb, threshold=0.75)
    assert merged[0].cross_platform is False and merged[0].platforms == ("amazon_corpus",)
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Append to `cross_platform.py`**

```python
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
```

- [ ] **Step 4: Run → pass.** **Step 5: Commit** `git commit -m "feat(G): cross-platform cluster merge by label-embedding cosine (union-find)"`

---

### Task G3: Agreement metric (`cross_platform.py` cont.)

**Files:** Modify `lacuna/aggregation/cross_platform.py`; Test `tests/aggregation/test_agreement.py`

- [ ] **Step 1: Failing test**

```python
# tests/aggregation/test_agreement.py
from lacuna.aggregation.cross_platform import MergedCluster, agreement_pct

def test_agreement_is_share_of_top_complaints_cross_platform():
    clusters = [
        MergedCluster("a", ("amazon_corpus", "hardcover"), 10, 5.0, 12, cross_platform=True),
        MergedCluster("b", ("amazon_corpus",), 8, 4.0, 9, cross_platform=False),
        MergedCluster("c", ("amazon_corpus", "hardcover"), 6, 3.0, 7, cross_platform=True),
        MergedCluster("d", ("hardcover",), 1, 0.5, 1, cross_platform=False),
    ]
    # top 3 by reviewer_count: a(10), b(8), c(6) -> 2 of 3 cross-platform
    assert abs(agreement_pct(clusters, top_n=3) - (2 / 3)) < 1e-9

def test_agreement_zero_when_empty():
    assert agreement_pct([], top_n=5) == 0.0
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Append to `cross_platform.py`**

```python
def agreement_pct(clusters: Sequence["MergedCluster"], *, top_n: int) -> float:
    """Share of a candidate's top-N complaints (by reviewer_count) confirmed on >1 platform."""
    if not clusters:
        return 0.0
    top = sorted(clusters, key=lambda c: c.reviewer_count, reverse=True)[:top_n]
    return sum(1 for c in top if c.cross_platform) / len(top)
```

- [ ] **Step 4: Run → pass.** **Step 5: Commit** `git commit -m "feat(G): cross_platform_agreement_pct metric"`

---

### Task G4: DB wrapper (integration — deferred)

**Files:** Create `lacuna/aggregation/persist.py` (skeleton)

```python
# lacuna/aggregation/persist.py
"""Read per-platform aspect_clusters -> merge -> upsert unified clusters with
cross_platform + platforms[]. Integration layer (needs Supabase + D embedder).
Pure merge logic is in cross_platform.py and fully unit-tested."""
from __future__ import annotations


async def fuse_project_clusters(project_id: str) -> None:  # pragma: no cover
    raise NotImplementedError("requires Supabase + local embedder; see cross_platform.merge_clusters")
```

- [ ] **Commit** `git commit -m "feat(G): aggregation persistence skeleton (deferred)"`

---

## Self-review (against PRD §9)

- Per-platform normalization BEFORE blend (z-score, zero-var safe) ✓ · merge by aspect-embedding similarity, `cross_platform=true` + `platforms[]` recorded ✓ · agreement is the credibility signal (`cross_platform_agreement_pct`) feeding confidence ✓ · no naive cross-culture rating blend ✓ · local-only (label embeddings via D, no raw text leaves machine) ✓ · pure & offline-testable with injected embedder ✓ · DB I/O isolated (deferred) ✓.
