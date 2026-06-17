# Workstream C — Seed & Works Grouping — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Implement the offline seed pipeline's deterministic cores — versioned normalization, 3-pass works grouping, and long-tail-aware review/work selection — plus a thin `seed.py` orchestrator that wires adapters → grouping → NLP → Supabase upsert.

**Architecture:** Pure, side-effect-free functions for everything algorithmic (normalization, grouping, selection) so they unit-test offline with no DB/network/models. `seed.py` is a thin orchestrator: it streams the corpus (adapter from B), applies the pure cores, calls the NLP module (D) and DB upserts. The orchestrator's DB/embedding calls are integration-tested later (needs Supabase + models); its pure helpers are tested now.

**Tech Stack:** stdlib `re`, `hashlib`; pydantic schemas (B); polars/duckdb available for the heavy join in the orchestrator. No external LLM (PRD §7).

**Depends on:** A, B. **Blocks:** D. **Not gated by G0** (only F/G/H are).

> **Design notes / approved defaults (documented in METHODOLOGY.md by Workstream J):**
> - `NORM_VERSION = 1`. A bump triggers full rebuild of affected works (PRD §6.4) — the orchestrator exposes `--rebuild`/`--reconcile`; only `--rebuild` is implemented now (full recompute), `--reconcile` raises NotImplementedError with a clear message (flagged).
> - Trigram similarity = Jaccard over character 3-grams; **tie-break merge threshold = 0.6** (PRD §6.3 says "title trigram similarity + exact author surname" without a number → approved default `works_trigram_threshold: 0.6`, added to `advanced.yaml`).
> - Critical review = `rating <= 3` (PRD §6.1.4). Cap = `curated_reviews_per_work` (15). Long-tail = `longtail_share` (0.3) of selected works must be low-review (PRD §6.5).
> - "Low-review work" threshold = `min_sample_gate` (20) reused as the low/high review-count boundary (approved; documented).

---

### Task C1: Versioned normalization (`lacuna/seed/normalization.py`)

**Files:**
- Create: `lacuna/seed/__init__.py` (empty)
- Create: `lacuna/seed/normalization.py`
- Test: `tests/seed/__init__.py` (empty), `tests/seed/test_normalization.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/seed/test_normalization.py
from lacuna.seed.normalization import (
    NORM_VERSION, normalize_title, normalize_author, normalized_key, author_surname,
)

def test_norm_version_is_int():
    assert isinstance(NORM_VERSION, int) and NORM_VERSION >= 1

def test_title_strips_subtitle_format_and_punct():
    # subtitle after ':' dropped, format token removed, punctuation/case normalized
    assert normalize_title("Meditations: A New Translation (Kindle Edition)") == "meditations"

def test_title_collapses_whitespace_and_series_tokens():
    assert normalize_title("Dune   Book  1") == "dune 1"

def test_author_surname_extracted():
    assert author_surname("Marcus Aurelius") == "aurelius"
    assert author_surname("") == ""

def test_normalized_key_combines_title_and_author():
    assert normalized_key("Meditations: X", "Marcus Aurelius") == "meditations|marcus aurelius"

def test_normalize_author_handles_none():
    assert normalize_author(None) == ""
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m uv run pytest tests/seed/test_normalization.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Write `lacuna/seed/__init__.py` (empty) and `lacuna/seed/normalization.py`**

```python
# lacuna/seed/normalization.py
"""Versioned title/author normalization (PRD §6.3). Bump NORM_VERSION to trigger
a full rebuild of affected works (handled by seed.py --rebuild)."""
from __future__ import annotations

import re

NORM_VERSION = 1

_SUBTITLE = re.compile(r":.*$")
_FORMAT_TOKENS = re.compile(
    r"\b(kindle|paperback|hardcover|audiobook|unabridged|abridged|illustrated|"
    r"edition|editions|volume|vol|book|series|reprint|annotated|deluxe)\b",
    re.IGNORECASE,
)
_PUNCT = re.compile(r"[^\w\s]")
_WS = re.compile(r"\s+")


def normalize_title(title: str) -> str:
    t = (title or "").strip()
    t = _SUBTITLE.sub("", t)          # drop subtitle after first ':'
    t = t.lower()
    t = _PUNCT.sub(" ", t)            # punctuation -> space
    t = _FORMAT_TOKENS.sub(" ", t)    # remove format/series tokens
    t = _WS.sub(" ", t).strip()
    return t


def normalize_author(author: str | None) -> str:
    a = (author or "").strip().lower()
    a = _PUNCT.sub(" ", a)
    a = _WS.sub(" ", a).strip()
    return a


def author_surname(author: str | None) -> str:
    a = normalize_author(author)
    return a.split(" ")[-1] if a else ""


def normalized_key(title: str, author: str | None) -> str:
    return f"{normalize_title(title)}|{normalize_author(author)}"
```

- [ ] **Step 4: Run it to verify it passes**

Run: `python -m uv run pytest tests/seed/test_normalization.py -v`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add lacuna/seed/__init__.py lacuna/seed/normalization.py tests/seed/__init__.py tests/seed/test_normalization.py
git commit -m "feat(C): versioned title/author normalization"
```

---

### Task C2: 3-pass works grouping (`lacuna/seed/works_grouping.py`)

**Files:**
- Create: `lacuna/seed/works_grouping.py`
- Test: `tests/seed/test_works_grouping.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/seed/test_works_grouping.py
from lacuna.seed.works_grouping import EditionInput, group_editions

def _ed(asin, parent, title, author):
    return EditionInput(asin=asin, parent_asin=parent, title=title, author=author)

def test_pass1_groups_by_parent_asin():
    eds = [_ed("A1", "P1", "Meditations", "Aurelius"),
           _ed("A2", "P1", "Meditations (Kindle)", "Aurelius")]
    groups = group_editions(eds)
    assert len(groups) == 1
    assert {e.asin for e in groups[0].members} == {"A1", "A2"}

def test_pass2_merges_by_normalized_key_across_parents():
    eds = [_ed("A1", "P1", "Meditations: A New Translation", "Marcus Aurelius"),
           _ed("A2", "P2", "Meditations (Paperback)", "Marcus Aurelius")]
    groups = group_editions(eds)
    assert len(groups) == 1

def test_pass3_keeps_separate_and_flags_when_below_trigram_threshold():
    eds = [_ed("A1", "P1", "Stoicism Today", "Smith"),
           _ed("A2", "P2", "Stoic Wisdom Forever", "Smith")]
    groups = group_editions(eds, trigram_threshold=0.6)
    # different titles, same surname, low trigram sim -> stay separate
    assert len(groups) == 2

def test_distinct_works_not_merged():
    eds = [_ed("A1", "P1", "Dune", "Herbert"),
           _ed("A2", "P2", "Meditations", "Aurelius")]
    assert len(group_editions(eds)) == 2
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m uv run pytest tests/seed/test_works_grouping.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Write `lacuna/seed/works_grouping.py`**

```python
# lacuna/seed/works_grouping.py
"""3-pass works grouping (PRD §6.3): parent_asin -> normalized_key -> trigram tie-break."""
from __future__ import annotations

from dataclasses import dataclass, field

from lacuna.seed.normalization import author_surname, normalize_title, normalized_key


@dataclass
class EditionInput:
    asin: str
    parent_asin: str | None
    title: str
    author: str | None


@dataclass
class WorkGroup:
    normalized_key: str
    title: str
    author: str | None
    members: list[EditionInput] = field(default_factory=list)
    flagged: bool = False  # tie-break uncertainty


def _trigrams(s: str) -> set[str]:
    s = f"  {s} "
    return {s[i:i + 3] for i in range(len(s) - 2)} if len(s) >= 3 else {s}


def trigram_similarity(a: str, b: str) -> float:
    ta, tb = _trigrams(a), _trigrams(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def group_editions(editions: list[EditionInput], *, trigram_threshold: float = 0.6) -> list[WorkGroup]:
    # Pass 1: group by shared parent_asin (fallback to own asin when parent missing).
    by_parent: dict[str, list[EditionInput]] = {}
    for ed in editions:
        key = ed.parent_asin or f"__solo__{ed.asin}"
        by_parent.setdefault(key, []).append(ed)

    # Build provisional groups, each keyed by the normalized_key of its first member.
    provisional: list[WorkGroup] = []
    for members in by_parent.values():
        head = members[0]
        provisional.append(WorkGroup(
            normalized_key=normalized_key(head.title, head.author),
            title=head.title, author=head.author, members=list(members),
        ))

    # Pass 2: merge provisional groups sharing an identical normalized_key.
    merged: dict[str, WorkGroup] = {}
    leftovers: list[WorkGroup] = []
    for grp in provisional:
        if grp.normalized_key in merged:
            merged[grp.normalized_key].members.extend(grp.members)
        else:
            merged[grp.normalized_key] = grp
    candidates = list(merged.values())

    # Pass 3: attempt cross-key merges only when title trigram sim >= threshold
    # AND author surname matches exactly; otherwise keep separate (flag if surname
    # matched but trigram failed — the ambiguous case).
    result: list[WorkGroup] = []
    for grp in candidates:
        placed = False
        for existing in result:
            same_surname = author_surname(grp.author) == author_surname(existing.author) and author_surname(grp.author) != ""
            sim = trigram_similarity(normalize_title(grp.title), normalize_title(existing.title))
            if same_surname and sim >= trigram_threshold:
                existing.members.extend(grp.members)
                placed = True
                break
            if same_surname and sim > 0:
                grp.flagged = True  # ambiguous: same author, partial title overlap
        if not placed:
            result.append(grp)
    return result
```

- [ ] **Step 4: Run it to verify it passes**

Run: `python -m uv run pytest tests/seed/test_works_grouping.py -v`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add lacuna/seed/works_grouping.py tests/seed/test_works_grouping.py
git commit -m "feat(C): 3-pass works grouping with trigram tie-break"
```

---

### Task C3: Review & work selection with long-tail (`lacuna/seed/selection.py`)

**Files:**
- Create: `lacuna/seed/selection.py`
- Test: `tests/seed/test_selection.py`

> Added module (PRD layout lists 3 seed files; selection is split out for testability — flagged in METHODOLOGY.md). Pure functions only.

- [ ] **Step 1: Write the failing test**

```python
# tests/seed/test_selection.py
from lacuna.seed.selection import select_critical_reviews, select_works_with_longtail

class R:
    def __init__(self, rating, helpful): self.rating = rating; self.helpful_vote = helpful

def test_critical_keeps_only_rating_le_3_ranked_by_helpful_capped():
    reviews = [R(5, 100), R(3, 1), R(2, 50), R(1, 10), R(4, 99)]
    out = select_critical_reviews(reviews, cap=2)
    assert [r.rating for r in out] == [2, 1]   # rating<=3, top-2 by helpful_vote
    assert all(r.rating <= 3 for r in out)

def test_critical_cap_respected():
    reviews = [R(1, i) for i in range(50)]
    assert len(select_critical_reviews(reviews, cap=15)) == 15

def test_longtail_includes_min_share_of_low_review_works():
    # 8 high-review works, 2 low-review works; ask for 5 works, 0.3 long-tail share
    works = [{"id": f"hi{i}", "review_count": 100} for i in range(8)] + \
            [{"id": f"lo{i}", "review_count": 2} for i in range(2)]
    selected = select_works_with_longtail(works, n=5, longtail_share=0.3, low_threshold=20)
    low = [w for w in selected if w["review_count"] < 20]
    assert len(selected) == 5
    assert len(low) >= 1   # ceil(5*0.3)=2 desired, but only 2 low exist -> >=1 guaranteed
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m uv run pytest tests/seed/test_selection.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Write `lacuna/seed/selection.py`**

```python
# lacuna/seed/selection.py
"""Pure selection helpers for the seed pass (PRD §6.1.4, §6.5)."""
from __future__ import annotations

import math
from typing import Any


def select_critical_reviews(reviews: list[Any], *, cap: int) -> list[Any]:
    """Keep critical reviews (rating <= 3), ranked by helpful_vote desc, capped."""
    critical = [r for r in reviews if (r.rating or 0) <= 3]
    critical.sort(key=lambda r: (r.helpful_vote or 0), reverse=True)
    return critical[:cap]


def select_works_with_longtail(
    works: list[dict], *, n: int, longtail_share: float, low_threshold: int,
) -> list[dict]:
    """Select n works ensuring at least ceil(n*longtail_share) low-review works,
    so survivorship bias does not re-enter at ingestion (PRD §6.5)."""
    low = [w for w in works if w["review_count"] < low_threshold]
    high = [w for w in works if w["review_count"] >= low_threshold]
    # high-review first by count desc; low-review by count desc too
    high.sort(key=lambda w: w["review_count"], reverse=True)
    low.sort(key=lambda w: w["review_count"], reverse=True)

    want_low = min(len(low), math.ceil(n * longtail_share))
    chosen = low[:want_low]
    chosen += high[: n - len(chosen)]
    # if still short (few high), backfill from remaining low
    if len(chosen) < n:
        chosen += low[want_low: want_low + (n - len(chosen))]
    return chosen[:n]
```

- [ ] **Step 4: Run it to verify it passes**

Run: `python -m uv run pytest tests/seed/test_selection.py -v`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add lacuna/seed/selection.py tests/seed/test_selection.py
git commit -m "feat(C): critical-review + long-tail work selection"
```

---

### Task C4: Edition extraction from corpus metadata (`lacuna/seed/seed.py` — pure part)

**Files:**
- Create: `lacuna/seed/seed.py`
- Test: `tests/seed/test_edition_extraction.py`

> `seed.py` holds both the pure `edition_from_meta()` extractor (tested now) and the integration `run_seed()` orchestrator (skeleton now, exercised after credentials+models exist).

- [ ] **Step 1: Write the failing test**

```python
# tests/seed/test_edition_extraction.py
from lacuna.seed.seed import edition_from_meta, infer_format

def test_infer_format_from_text():
    assert infer_format("Kindle Edition") == "kindle"
    assert infer_format("Paperback") == "paperback"
    assert infer_format("Audible Audiobook") == "audiobook"
    assert infer_format("Mass Market") == "other"

def test_edition_from_meta_extracts_fields():
    row = {"parent_asin": "P1", "asin": "A1", "title": "Meditations",
           "author": {"name": "Aurelius"}, "price": "12.99",
           "details": {"format": "Paperback"}}
    ed = edition_from_meta(row)
    assert ed.asin == "A1" and ed.parent_asin == "P1"
    assert ed.price_cents == 1299
    assert ed.format == "paperback"

def test_edition_from_meta_tolerates_missing_price():
    ed = edition_from_meta({"asin": "A2", "title": "X"})
    assert ed.price_cents is None and ed.format == "other"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m uv run pytest tests/seed/test_edition_extraction.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Write `lacuna/seed/seed.py`**

```python
# lacuna/seed/seed.py
"""Offline seed orchestrator (PRD §6). Pure helpers are unit-tested; run_seed()
is the integration entrypoint (DB upsert + local NLP) exercised after Supabase +
models are available. NO external LLM is called here (PRD §7)."""
from __future__ import annotations

import re
from dataclasses import dataclass

from lacuna.seed.works_grouping import EditionInput

_FORMAT_MAP = [
    ("kindle", "kindle"), ("audiobook", "audiobook"), ("audible", "audiobook"),
    ("paperback", "paperback"), ("hardcover", "hardcover"), ("hardback", "hardcover"),
]


@dataclass
class EditionRecord:
    asin: str
    parent_asin: str | None
    title: str
    author: str | None
    isbn13: str | None
    isbn10: str | None
    format: str
    price_cents: int | None


def infer_format(text: str | None) -> str:
    t = (text or "").lower()
    for needle, fmt in _FORMAT_MAP:
        if needle in t:
            return fmt
    return "other"


def _price_to_cents(price) -> int | None:
    if price is None:
        return None
    try:
        return round(float(re.sub(r"[^0-9.]", "", str(price))) * 100)
    except (ValueError, TypeError):
        return None


def edition_from_meta(row: dict) -> EditionRecord:
    author = row.get("author")
    author_name = author.get("name") if isinstance(author, dict) else author
    details = row.get("details") or {}
    fmt_src = details.get("format") or row.get("format") or ""
    return EditionRecord(
        asin=row.get("asin", ""),
        parent_asin=row.get("parent_asin"),
        title=row.get("title", ""),
        author=author_name,
        isbn13=details.get("isbn_13") or row.get("isbn13"),
        isbn10=details.get("isbn_10") or row.get("isbn10"),
        format=infer_format(fmt_src),
        price_cents=_price_to_cents(row.get("price")),
    )


def to_edition_input(rec: EditionRecord) -> EditionInput:
    return EditionInput(asin=rec.asin, parent_asin=rec.parent_asin,
                        title=rec.title, author=rec.author)


def run_seed(rebuild: bool = False, reconcile: bool = False) -> None:  # pragma: no cover
    """Integration entrypoint (deferred). Streams corpus -> editions -> works ->
    critical review selection -> local embed/cluster/label (Workstream D) -> upsert
    to Supabase -> analysis_runs(mode='seed'). Requires DATABASE_URL + pinned models."""
    if reconcile:
        raise NotImplementedError(
            "--reconcile not implemented; use --rebuild for a full recompute (PRD §6.4)")
    raise NotImplementedError(
        "run_seed requires Supabase credentials and pinned models; run after `alembic upgrade head`")
```

- [ ] **Step 4: Run it to verify it passes**

Run: `python -m uv run pytest tests/seed/test_edition_extraction.py -v`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add lacuna/seed/seed.py tests/seed/test_edition_extraction.py
git commit -m "feat(C): edition extraction + seed orchestrator skeleton (integration deferred)"
```

---

### Task C5: Add `works_trigram_threshold` to advanced.yaml

**Files:**
- Modify: `config/advanced.yaml`
- Test: `tests/seed/test_config_knob.py`

> The pin script rewrote `advanced.yaml` (comments stripped). Add the knob as a new key.

- [ ] **Step 1: Write the failing test**

```python
# tests/seed/test_config_knob.py
from lacuna.config import load_advanced

def test_works_trigram_threshold_present():
    adv = load_advanced()
    assert adv.get("works_trigram_threshold") == 0.6
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m uv run pytest tests/seed/test_config_knob.py -v`
Expected: FAIL — key missing.

- [ ] **Step 3: Add the key to `config/advanced.yaml`**

Add this line near the other tuning knobs (e.g. after `longtail_share`):
```yaml
works_trigram_threshold: 0.6   # §6.3 tie-break: min title trigram Jaccard to merge same-author editions
```

- [ ] **Step 4: Run it to verify it passes**

Run: `python -m uv run pytest tests/seed/test_config_knob.py -v`
Expected: passed.

- [ ] **Step 5: Commit**

```bash
git add config/advanced.yaml tests/seed/test_config_knob.py
git commit -m "feat(C): add works_trigram_threshold knob"
```

---

## Self-review (against PRD)

- **§6.3 grouping** — 3 passes implemented (parent_asin → normalized_key → trigram+surname tie-break); ambiguous case flagged. ✓
- **§6.4 versioning** — `NORM_VERSION` constant; `--reconcile` raises a clear NotImplementedError (flagged); `--rebuild` is the supported path. ✓
- **§6.1.4 / §6.5 selection** — critical filter (≤3), helpful ranking, cap, long-tail share. ✓
- **§7 local boundary** — no external LLM anywhere in seed. ✓
- **Deferred (integration):** `run_seed()` DB upsert + embed/cluster (needs Supabase + models) — clearly marked, raises rather than silently no-ops. ✓
- **Added knob** `works_trigram_threshold` surfaced in config + to be documented in METHODOLOGY.md. ✓
- **Placeholder scan** — complete code in every step. ✓

**Offline-testable now:** C1–C5. **Deferred to credential/model step:** `run_seed()` end-to-end.
