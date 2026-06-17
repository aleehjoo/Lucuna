# Workstream D — Local NLP — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Implement the strictly-local, $0 NLP pipeline — embeddings (hash-cached), HDBSCAN clustering (cosine), and zero-shot aspect labeling — with **no external LLM API ever** (PRD §7). Pure/algorithmic cores and the caching + label-selection logic are unit-tested offline with injected fakes; the real model loads (MiniLM, bart-large-mnli) are thin wrappers exercised after the pinned models are downloaded.

**Architecture:** Dependency injection everywhere a model is used, so cores test offline:
- `embeddings.py` — `Embedder(encoder=None)`: a hash cache + batching layer over an `encoder` callable. Default encoder lazily loads `all-MiniLM-L6-v2` at the pinned revision; tests inject a fake encoder.
- `clustering.py` — pure functions over vectors (hdbscan + sklearn, both installed); no model needed.
- `aspects.py` — `AspectLabeler(classifier=None)`: pure label-selection over zero-shot scores; default classifier lazily loads `bart-large-mnli` at the pinned revision; tests inject a fake classifier.

**Tech Stack:** numpy, scikit-learn, hdbscan, hashlib; (lazy) sentence-transformers, transformers. Revisions read from `config/advanced.yaml` (pinned in Workstream A).

**Depends on:** A, C. **Blocks:** F, G. **Not gated by G0** for code; real runs come after credentials/models.

> **Design notes (from Context7 + Sequential Thinking):**
> - HDBSCAN clusters via a **precomputed cosine distance matrix** (`sklearn.metrics.pairwise_distances(metric="cosine")`, float64) with `metric="precomputed"`. Noise points get label `-1`.
> - Per-work corpora are tiny (≤15 curated reviews), so `min_cluster_size` defaults to **2**; when `n < min_cluster_size` we return all-noise (`-1`) rather than crash (small-n guard).
> - Aspect taxonomy from PRD §7: `outdated, too_basic, too_advanced, poor_examples, inaccurate, badly_structured, overpriced, repetitive`. Labels are **paraphrased**; **no raw review quote** is ever persisted/exported (PRD §7, ToU).

---

### Task D1: Embeddings with hash cache (`lacuna/nlp/embeddings.py`)

**Files:**
- Create: `lacuna/nlp/__init__.py` (empty)
- Create: `lacuna/nlp/embeddings.py`
- Test: `tests/nlp/__init__.py` (empty), `tests/nlp/test_embeddings.py`

- [ ] **Step 1: Write the failing test** (inject a fake encoder — no model download)

```python
# tests/nlp/test_embeddings.py
import numpy as np
from lacuna.nlp.embeddings import Embedder, review_hash

def test_review_hash_stable_and_unique():
    assert review_hash("abc") == review_hash("abc")
    assert review_hash("abc") != review_hash("abd")

def test_embedder_uses_cache_and_calls_encoder_once_per_unique():
    calls = []
    def fake_encoder(texts):
        calls.append(list(texts))
        return np.array([[float(len(t))] * 3 for t in texts])
    emb = Embedder(encoder=fake_encoder)
    out1 = emb.encode(["hello", "hi"])
    out2 = emb.encode(["hello", "hi"])   # second call fully cached
    assert out1.shape == (2, 3)
    np.testing.assert_array_equal(out1, out2)
    # encoder called only for the first batch (both unique), not the cached second
    assert len(calls) == 1

def test_embedder_only_encodes_uncached_subset():
    calls = []
    def fake_encoder(texts):
        calls.append(list(texts)); return np.array([[1.0, 2.0, 3.0]] * len(texts))
    emb = Embedder(encoder=fake_encoder)
    emb.encode(["a"])
    emb.encode(["a", "b"])   # only "b" is new
    assert calls[-1] == ["b"]
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m uv run pytest tests/nlp/test_embeddings.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Write `lacuna/nlp/__init__.py` (empty) and `lacuna/nlp/embeddings.py`**

```python
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
```

- [ ] **Step 4: Run it to verify it passes**

Run: `python -m uv run pytest tests/nlp/test_embeddings.py -v`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add lacuna/nlp/__init__.py lacuna/nlp/embeddings.py tests/nlp/__init__.py tests/nlp/test_embeddings.py
git commit -m "feat(D): local embeddings with hash cache (injectable encoder)"
```

---

### Task D2: HDBSCAN clustering (`lacuna/nlp/clustering.py`)

**Files:**
- Create: `lacuna/nlp/clustering.py`
- Test: `tests/nlp/test_clustering.py`

- [ ] **Step 1: Write the failing test** (synthetic vectors — no model)

```python
# tests/nlp/test_clustering.py
import numpy as np
from lacuna.nlp.clustering import cluster_embeddings, members_by_cluster

def test_two_separated_groups_form_clusters():
    # two tight groups in cosine space
    g1 = np.tile(np.array([1.0, 0.0, 0.0]), (5, 1)) + np.random.RandomState(0).normal(0, 1e-3, (5, 3))
    g2 = np.tile(np.array([0.0, 1.0, 0.0]), (5, 1)) + np.random.RandomState(1).normal(0, 1e-3, (5, 3))
    labels = cluster_embeddings(np.vstack([g1, g2]), min_cluster_size=2)
    # at least 2 distinct non-noise clusters
    assert len({l for l in labels if l != -1}) >= 2

def test_small_n_returns_all_noise():
    labels = cluster_embeddings(np.array([[1.0, 0.0, 0.0]]), min_cluster_size=2)
    assert list(labels) == [-1]

def test_members_by_cluster_excludes_noise():
    labels = np.array([-1, 0, 0, 1, -1])
    m = members_by_cluster(labels)
    assert m == {0: [1, 2], 1: [3]}
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m uv run pytest tests/nlp/test_clustering.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Write `lacuna/nlp/clustering.py`**

```python
# lacuna/nlp/clustering.py
"""HDBSCAN clustering over embeddings in cosine space (PRD §7). Pure; no model."""
from __future__ import annotations

import hdbscan
import numpy as np
from sklearn.metrics import pairwise_distances


def cluster_embeddings(vectors, min_cluster_size: int = 2) -> np.ndarray:
    """Return a cluster label per row; noise = -1. Uses a precomputed cosine
    distance matrix. Guards small n (< min_cluster_size) by returning all-noise."""
    X = np.asarray(vectors, dtype="float64")
    if X.ndim != 2 or len(X) < min_cluster_size:
        return np.full(len(X), -1, dtype=int)
    distances = pairwise_distances(X, metric="cosine").astype("float64")
    clusterer = hdbscan.HDBSCAN(min_cluster_size=min_cluster_size, metric="precomputed")
    return clusterer.fit_predict(distances)


def members_by_cluster(labels) -> dict[int, list[int]]:
    """Map cluster_id -> member row indices, excluding noise (-1)."""
    out: dict[int, list[int]] = {}
    for idx, lab in enumerate(labels):
        lab = int(lab)
        if lab == -1:
            continue
        out.setdefault(lab, []).append(idx)
    return out
```

- [ ] **Step 4: Run it to verify it passes**

Run: `python -m uv run pytest tests/nlp/test_clustering.py -v`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add lacuna/nlp/clustering.py tests/nlp/test_clustering.py
git commit -m "feat(D): HDBSCAN cosine clustering with small-n guard"
```

---

### Task D3: Zero-shot aspect labeling (`lacuna/nlp/aspects.py`)

**Files:**
- Create: `lacuna/nlp/aspects.py`
- Test: `tests/nlp/test_aspects.py`

- [ ] **Step 1: Write the failing test** (inject a fake classifier — no bart download)

```python
# tests/nlp/test_aspects.py
from lacuna.nlp.aspects import AspectLabeler, ASPECT_TAXONOMY, pick_aspect

def test_aspect_taxonomy_matches_prd():
    assert ASPECT_TAXONOMY == [
        "outdated", "too_basic", "too_advanced", "poor_examples",
        "inaccurate", "badly_structured", "overpriced", "repetitive",
    ]

def test_pick_aspect_returns_highest():
    label, score = pick_aspect({"outdated": 0.2, "overpriced": 0.7, "repetitive": 0.1})
    assert label == "overpriced" and score == 0.7

def test_labeler_labels_cluster_with_injected_classifier():
    # fake zero-shot: returns dict label->score for given texts
    def fake_clf(text, candidate_labels):
        return {lab: (0.9 if lab == "outdated" else 0.05) for lab in candidate_labels}
    labeler = AspectLabeler(classifier=fake_clf)
    result = labeler.label_cluster(["the examples are from 2009", "outdated references"])
    assert result.label == "outdated"
    assert result.score >= 0.5
    # representative is a paraphrase, never a raw quote
    assert "examples are from 2009" not in result.representative
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m uv run pytest tests/nlp/test_aspects.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Write `lacuna/nlp/aspects.py`**

```python
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
```

- [ ] **Step 4: Run it to verify it passes**

Run: `python -m uv run pytest tests/nlp/test_aspects.py -v`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add lacuna/nlp/aspects.py tests/nlp/test_aspects.py
git commit -m "feat(D): zero-shot aspect labeling, paraphrased (injectable classifier)"
```

---

### Task D4: Real-model smoke test (deferred-but-specified)

**Files:**
- Create: `tests/nlp/test_models_smoke.py`

> Guarded by an env flag so it only runs when the heavy models are downloaded; keeps the default suite at $0/offline. Proves the lazy default encoder/classifier load at the pinned revision.

- [ ] **Step 1: Write the guarded smoke test**

```python
# tests/nlp/test_models_smoke.py
import os
import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("LACUNA_RUN_MODEL_SMOKE") != "1",
    reason="set LACUNA_RUN_MODEL_SMOKE=1 to run heavy model smoke tests (downloads weights)",
)

def test_minilm_encodes_384():
    from lacuna.nlp.embeddings import Embedder, EMBED_DIM
    out = Embedder().encode(["a sentence", "another"])
    assert out.shape == (2, EMBED_DIM)

def test_bart_zero_shot_labels():
    from lacuna.nlp.aspects import AspectLabeler
    res = AspectLabeler().label_cluster(["the price is far too high for what you get"])
    assert res.label  # any taxonomy label
```

- [ ] **Step 2: Run it (skipped by default)**

Run: `python -m uv run pytest tests/nlp/test_models_smoke.py -v`
Expected: 2 skipped.

To actually exercise it later (after models are cached): `LACUNA_RUN_MODEL_SMOKE=1 python -m uv run pytest tests/nlp/test_models_smoke.py -v`.

- [ ] **Step 3: Commit**

```bash
git add tests/nlp/test_models_smoke.py
git commit -m "test(D): guarded real-model smoke tests (skipped by default, $0 suite)"
```

---

## Self-review (against PRD)

- **§7 local-only** — no external LLM anywhere; MiniLM + bart load locally at pinned revisions; the only Anthropic call lives in `export/` (Workstream H), not here. ✓
- **Embeddings** — hash-cached, batched, injectable; 384-dim. ✓
- **Clustering** — HDBSCAN cosine (precomputed), noise = -1, small-n guard. ✓
- **Aspects** — PRD taxonomy exactly; paraphrased label + representative; no raw quote persisted (test asserts it). ✓
- **Pinned revisions** — both loaders read the pinned revision and fail loud if placeholder. ✓
- **$0 default suite** — heavy model tests skipped unless `LACUNA_RUN_MODEL_SMOKE=1`. ✓
- **Placeholder scan** — complete code; deferred default-loaders are real (lazy), not stubs. ✓

**Offline-testable now:** D1–D4 (D4 skips). **Deferred:** real MiniLM/bart runs (D4 with the env flag) + persistence of clusters to `aspect_clusters` (happens in `seed.run_seed` / analyze pipeline, after credentials).
