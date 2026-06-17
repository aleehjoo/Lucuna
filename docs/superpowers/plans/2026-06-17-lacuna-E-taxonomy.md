# Workstream E — Taxonomy — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Implement the BISAC canonical spine and the crosswalk matching **decision logic** (auto-accept / auto-reject / queue-to-unmapped), with a Google-Books-anchored learning entrypoint whose embedding + DB persistence is integration-deferred.

**Architecture:** `bisac.py` holds a canonical BISAC reference (format validator + a seed label map, extensible) — pure. `crosswalk.py` holds the pure `classify_match(similarity)` decision and a thin `learn_crosswalk()` integration entrypoint (embeds source labels with MiniLM, compares to canonical labels, persists to `taxonomy_crosswalk`/`unmapped_labels`) deferred until models + Supabase exist.

**Tech Stack:** stdlib `re`; (deferred) sentence-transformers + DB.

**Depends on:** A, B. **Blocks:** F. **Not gated by G0.**

> **Design notes / approved defaults (documented in METHODOLOGY.md):**
> - `crosswalk_auto_accept: 0.85` exists in `advanced.yaml`. PRD §13 also states "below 0.55 → auto-reject" in a comment but ships no key → add **`crosswalk_auto_reject: 0.55`** (approved). Band `[0.55, 0.85)` → queue to `unmapped_labels`.
> - BISAC is proprietary/large; we ship a **format validator** + a **small seed label map** for the example niches and extend via learning. Documented as a deliberate subset, not the full BISAC catalog.

---

### Task E1: BISAC canonical spine (`lacuna/taxonomy/bisac.py`)

**Files:**
- Create: `lacuna/taxonomy/__init__.py` (empty)
- Create: `lacuna/taxonomy/bisac.py`
- Test: `tests/taxonomy/__init__.py` (empty), `tests/taxonomy/test_bisac.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/taxonomy/test_bisac.py
from lacuna.taxonomy.bisac import is_valid_bisac, canonical_label, SEED_BISAC

def test_format_validation():
    assert is_valid_bisac("SEL036000") is True
    assert is_valid_bisac("PHI011000") is True
    assert is_valid_bisac("sel036000") is False   # must be uppercase 3 letters + 6 digits
    assert is_valid_bisac("SEL36000") is False     # wrong digit count
    assert is_valid_bisac("") is False

def test_seed_labels_present_and_resolvable():
    assert "SEL036000" in SEED_BISAC
    assert canonical_label("SEL036000")  # non-empty
    assert canonical_label("ZZZ999999") is None   # unknown code
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m uv run pytest tests/taxonomy/test_bisac.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Write `lacuna/taxonomy/__init__.py` (empty) and `lacuna/taxonomy/bisac.py`**

```python
# lacuna/taxonomy/bisac.py
"""BISAC canonical spine. Ships a format validator + a small seed label map for the
example niches; the full BISAC catalog is proprietary, so the crosswalk learns the
rest (PRD §5/§9). Extend SEED_BISAC as needed."""
from __future__ import annotations

import re

_BISAC_RE = re.compile(r"^[A-Z]{3}\d{6}$")

# Seed subset (code -> canonical human label). Deliberately small; extended by learning.
SEED_BISAC: dict[str, str] = {
    "SEL036000": "Self-Help / Personal Growth / General",
    "SEL024000": "Self-Help / Motivational & Inspirational",
    "SEL027000": "Self-Help / Personal Growth / Success",
    "PHI011000": "Philosophy / Movements / Stoicism",
    "PHI000000": "Philosophy / General",
    "BUS019000": "Business & Economics / Decision-Making & Problem Solving",
    "PSY000000": "Psychology / General",
    "OCC011000": "Body, Mind & Spirit / Mindfulness & Meditation",
}


def is_valid_bisac(code: str) -> bool:
    return bool(code) and bool(_BISAC_RE.match(code))


def canonical_label(code: str) -> str | None:
    return SEED_BISAC.get(code)
```

- [ ] **Step 4: Run it to verify it passes**

Run: `python -m uv run pytest tests/taxonomy/test_bisac.py -v`
Expected: passed.

- [ ] **Step 5: Commit**

```bash
git add lacuna/taxonomy/__init__.py lacuna/taxonomy/bisac.py tests/taxonomy/__init__.py tests/taxonomy/test_bisac.py
git commit -m "feat(E): BISAC spine (format validator + seed label map)"
```

---

### Task E2: Crosswalk decision logic (`lacuna/taxonomy/crosswalk.py`)

**Files:**
- Create: `lacuna/taxonomy/crosswalk.py`
- Test: `tests/taxonomy/test_crosswalk.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/taxonomy/test_crosswalk.py
import pytest
from lacuna.taxonomy.crosswalk import classify_match, best_match, MatchDecision

def test_classify_accept_reject_queue():
    assert classify_match(0.90, accept=0.85, reject=0.55) == MatchDecision.ACCEPT
    assert classify_match(0.85, accept=0.85, reject=0.55) == MatchDecision.ACCEPT  # boundary inclusive
    assert classify_match(0.70, accept=0.85, reject=0.55) == MatchDecision.QUEUE
    assert classify_match(0.55, accept=0.85, reject=0.55) == MatchDecision.QUEUE   # >= reject -> queue
    assert classify_match(0.40, accept=0.85, reject=0.55) == MatchDecision.REJECT

def test_best_match_picks_highest_similarity():
    sims = {"SEL036000": 0.62, "PHI011000": 0.91, "BUS019000": 0.30}
    code, sim = best_match(sims)
    assert code == "PHI011000" and sim == 0.91

def test_best_match_empty_returns_none():
    assert best_match({}) == (None, 0.0)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m uv run pytest tests/taxonomy/test_crosswalk.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Write `lacuna/taxonomy/crosswalk.py`**

```python
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
```

- [ ] **Step 4: Run it to verify it passes**

Run: `python -m uv run pytest tests/taxonomy/test_crosswalk.py -v`
Expected: passed.

- [ ] **Step 5: Commit**

```bash
git add lacuna/taxonomy/crosswalk.py tests/taxonomy/test_crosswalk.py
git commit -m "feat(E): crosswalk accept/reject/queue decision logic"
```

---

### Task E3: Add `crosswalk_auto_reject` knob

**Files:**
- Modify: `config/advanced.yaml`
- Test: `tests/taxonomy/test_crosswalk_knob.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/taxonomy/test_crosswalk_knob.py
from lacuna.config import load_advanced

def test_crosswalk_reject_knob_present():
    adv = load_advanced()
    assert adv.get("crosswalk_auto_accept") == 0.85
    assert adv.get("crosswalk_auto_reject") == 0.55
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m uv run pytest tests/taxonomy/test_crosswalk_knob.py -v`
Expected: FAIL — key missing.

- [ ] **Step 3: Add the key to `config/advanced.yaml`**

Add directly after the `crosswalk_auto_accept` line:
```yaml
crosswalk_auto_reject: 0.55    # cosine below this -> auto-reject; [0.55,0.85) -> unmapped queue (§13)
```

- [ ] **Step 4: Run it to verify it passes**

Run: `python -m uv run pytest tests/taxonomy/test_crosswalk_knob.py -v`
Expected: passed.

- [ ] **Step 5: Commit**

```bash
git add config/advanced.yaml tests/taxonomy/test_crosswalk_knob.py
git commit -m "feat(E): add crosswalk_auto_reject knob"
```

---

## Self-review (against PRD)

- **§5 taxonomy tables** — decision logic maps to `taxonomy_crosswalk` (accept/reject) and `unmapped_labels` (queue); persistence deferred but clearly specified. ✓
- **§9 Google-Books-anchored** — `learn_crosswalk` documents the bootstrap path; categories are BISAC-derived. ✓
- **§13 thresholds** — accept 0.85, reject 0.55, queue band; both knobs in config. ✓
- **BISAC subset** — flagged as deliberate seed + format validator; learning extends it. ✓
- **Placeholder scan** — complete code; deferred functions raise with clear messages, not silent pass. ✓

**Offline-testable now:** E1–E3. **Deferred:** `learn_crosswalk()` embedding + persistence.
