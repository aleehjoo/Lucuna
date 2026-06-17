# Workstream B — Adapters — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement every external-source client behind a pydantic boundary, each with its own rate/retry policy (exponential backoff + jitter on 429/5xx, honoring `Retry-After`), so a source changing shape fails loud and swapping a source is a one-file change.

**Architecture:** A shared async HTTP helper (`adapters/_http.py`) provides a rate-limited, backoff-wrapped `httpx.AsyncClient`. Each adapter (`hardcover`, `google_books`, `nyt`, `open_library`, `corpus`) returns pydantic-v2-validated models from `schemas/`. Contract tests use `respx` to replay a recorded response per source and assert the parser. The Amazon corpus adapter streams Hugging Face parquet (no script loader, no `trust_remote_code`).

**Tech Stack:** httpx, gql (httpx transport) for Hardcover GraphQL, tenacity for backoff, pydantic v2, datasets (streaming), respx (tests).

**Depends on:** A. **Blocks:** G0 (needs the Hardcover adapter), C, E, G.

> **Design notes:** PRD §4 limits — Hardcover **60/min**, 30s timeout, Bearer token *without* `Bearer ` prefix (config stores the raw `eyJ…`), descriptive User-Agent; NYT 10/min (~6s spacing), 4000/day; Google Books ~1000/day; Open Library "be polite" + descriptive UA. Validation lives at the boundary (PRD §15). Corpus: load raw parquet configs `raw_review_Books` / `raw_meta_Books` with the pinned revision, `streaming=True`, never full-download, never commit text.

---

### Task B1: Shared HTTP helper — rate limit + backoff (`adapters/_http.py`)

**Files:**
- Create: `lacuna/adapters/__init__.py`
- Create: `lacuna/adapters/_http.py`
- Test: `tests/adapters/test_http.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/adapters/test_http.py
import httpx, respx, pytest
from lacuna.adapters._http import request_with_backoff, RateLimiter

@respx.mock
async def test_retries_on_429_then_succeeds():
    route = respx.get("https://x.test/a")
    route.side_effect = [
        httpx.Response(429, headers={"Retry-After": "0"}),
        httpx.Response(200, json={"ok": True}),
    ]
    async with httpx.AsyncClient() as c:
        resp = await request_with_backoff(c, "GET", "https://x.test/a", max_attempts=3)
    assert resp.status_code == 200
    assert route.call_count == 2

@respx.mock
async def test_gives_up_and_raises_after_max_attempts():
    respx.get("https://x.test/b").mock(return_value=httpx.Response(503))
    async with httpx.AsyncClient() as c:
        with pytest.raises(httpx.HTTPStatusError):
            await request_with_backoff(c, "GET", "https://x.test/b", max_attempts=2, base_delay=0)

async def test_rate_limiter_spaces_calls():
    import time
    rl = RateLimiter(per_minute=600)  # 0.1s spacing
    t0 = time.monotonic()
    await rl.acquire(); await rl.acquire()
    assert time.monotonic() - t0 >= 0.09
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/adapters/test_http.py -v`
Expected: FAIL — module missing. *(Create `tests/adapters/__init__.py` empty if needed.)*

- [ ] **Step 3: Write `lacuna/adapters/__init__.py` (empty) and `lacuna/adapters/_http.py`**

```python
# lacuna/adapters/_http.py
from __future__ import annotations

import asyncio
import random
import time

import httpx

USER_AGENT = "Lacuna/0.1 (reader-gap research; +https://github.com/lacuna)"
RETRY_STATUS = {429, 500, 502, 503, 504}


class RateLimiter:
    """Simple async min-interval limiter (token spacing)."""
    def __init__(self, per_minute: int):
        self._interval = 60.0 / per_minute
        self._last = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            wait = self._interval - (now - self._last)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = time.monotonic()


async def request_with_backoff(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    max_attempts: int = 5,
    base_delay: float = 0.5,
    limiter: RateLimiter | None = None,
    **kwargs,
) -> httpx.Response:
    """Issue a request, retrying RETRY_STATUS with exponential backoff + jitter,
    honoring Retry-After. Raises httpx.HTTPStatusError on terminal failure."""
    headers = {"User-Agent": USER_AGENT, **kwargs.pop("headers", {})}
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        if limiter:
            await limiter.acquire()
        resp = await client.request(method, url, headers=headers, **kwargs)
        if resp.status_code in RETRY_STATUS and attempt < max_attempts:
            retry_after = resp.headers.get("Retry-After")
            delay = float(retry_after) if retry_after and retry_after.isdigit() \
                else base_delay * (2 ** (attempt - 1)) + random.uniform(0, base_delay)
            await asyncio.sleep(delay)
            last_exc = httpx.HTTPStatusError("retryable", request=resp.request, response=resp)
            continue
        resp.raise_for_status()
        return resp
    assert last_exc is not None
    raise last_exc
```

- [ ] **Step 4: Run it to verify it passes**

Run: `uv run pytest tests/adapters/test_http.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add lacuna/adapters/__init__.py lacuna/adapters/_http.py tests/adapters/__init__.py tests/adapters/test_http.py
git commit -m "feat: shared async HTTP helper (rate limit + backoff + Retry-After)"
```

---

### Task B2: Boundary schemas (`lacuna/schemas/`)

**Files:**
- Create: `lacuna/schemas/__init__.py`
- Create: `lacuna/schemas/sources.py`
- Test: `tests/test_schemas.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_schemas.py
import pytest
from pydantic import ValidationError
from lacuna.schemas.sources import (
    HardcoverReview, GoogleVolume, NytBestseller, OpenLibraryDoc, CorpusReview,
)

def test_hardcover_review_parses_minimal():
    r = HardcoverReview(id=1, rating=2.0, body="weak examples", user_id=7)
    assert r.rating == 2.0 and r.user_id == 7

def test_google_volume_extracts_ratings_count():
    v = GoogleVolume.model_validate({
        "volumeInfo": {"title": "X", "categories": ["Self-Help / Personal Growth"],
                       "averageRating": 4.1, "ratingsCount": 12},
    })
    assert v.ratings_count == 12 and v.categories == ["Self-Help / Personal Growth"]

def test_shape_drift_fails_loud():
    with pytest.raises(ValidationError):
        NytBestseller.model_validate({"unexpected": "shape"})
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_schemas.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Write `lacuna/schemas/__init__.py` (empty) and `lacuna/schemas/sources.py`**

```python
# lacuna/schemas/sources.py
"""Pydantic v2 boundary models. A source changing shape fails loud here (PRD §15)."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator


class HardcoverReview(BaseModel):
    id: int
    rating: float | None = None
    body: str | None = None
    user_id: int | None = None
    created_at: datetime | None = None


class GoogleVolume(BaseModel):
    title: str
    categories: list[str] = Field(default_factory=list)
    average_rating: float | None = None
    ratings_count: int = 0

    @classmethod
    def model_validate(cls, obj, **kw):  # accept raw Google volume shape
        if isinstance(obj, dict) and "volumeInfo" in obj:
            vi = obj["volumeInfo"]
            obj = {
                "title": vi.get("title", ""),
                "categories": vi.get("categories", []),
                "average_rating": vi.get("averageRating"),
                "ratings_count": vi.get("ratingsCount", 0),
            }
        return super().model_validate(obj, **kw)


class NytBestseller(BaseModel):
    title: str
    weeks_on_list: int = 0
    rank: int | None = None


class OpenLibraryDoc(BaseModel):
    title: str
    first_publish_year: int | None = None
    edition_count: int = 0


class CorpusReview(BaseModel):
    """One McAuley raw_review_Books row (subset we keep)."""
    asin: str
    parent_asin: str | None = None
    rating: float
    title: str | None = None
    text: str
    helpful_vote: int = 0
    timestamp: int | None = None  # epoch ms
    user_id: str | None = None

    @field_validator("rating")
    @classmethod
    def rating_in_range(cls, v: float) -> float:
        if not 0 <= v <= 5:
            raise ValueError(f"rating {v} out of 0–5")
        return v

    @property
    def review_date(self) -> datetime | None:
        from datetime import timezone
        return datetime.fromtimestamp(self.timestamp / 1000, tz=timezone.utc) if self.timestamp else None
```

- [ ] **Step 4: Run it to verify it passes**

Run: `uv run pytest tests/test_schemas.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add lacuna/schemas/__init__.py lacuna/schemas/sources.py tests/test_schemas.py
git commit -m "feat: pydantic boundary schemas for all sources"
```

---

### Task B3: Hardcover adapter (`adapters/hardcover.py`)

**Files:**
- Create: `lacuna/adapters/hardcover.py`
- Test: `tests/adapters/test_hardcover.py`

> The GraphQL endpoint is `https://api.hardcover.app/v1/graphql`; auth is `Authorization: Bearer <token>` where the stored token is the raw `eyJ…` (no `Bearer ` prefix). Limiter at 60/min.

- [ ] **Step 1: Write the failing test** (recorded GraphQL response replayed via respx)

```python
# tests/adapters/test_hardcover.py
import httpx, respx
from lacuna.adapters.hardcover import HardcoverClient

RECORDED = {
  "data": {"books": [{
      "id": 42, "title": "Meditations",
      "reviews": [
        {"id": 1, "rating": 2.0, "body": "translation is clunky", "user_id": 5, "created_at": "2025-01-02T00:00:00Z"},
        {"id": 2, "rating": 5.0, "body": "great", "user_id": 6, "created_at": "2025-02-02T00:00:00Z"},
      ],
  }]}
}

@respx.mock
async def test_fetch_reviews_by_title_parses_recorded():
    respx.post("https://api.hardcover.app/v1/graphql").mock(
        return_value=httpx.Response(200, json=RECORDED))
    client = HardcoverClient(token="eyJ-fake")
    book = await client.fetch_book_by_title("Meditations")
    assert book.title == "Meditations"
    assert len(book.reviews) == 2
    assert book.reviews[0].body == "translation is clunky"
    await client.aclose()

@respx.mock
async def test_auth_header_has_no_double_bearer():
    captured = {}
    def _capture(request):
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"data": {"books": []}})
    respx.post("https://api.hardcover.app/v1/graphql").mock(side_effect=_capture)
    client = HardcoverClient(token="eyJ-fake")
    await client.fetch_book_by_title("x")
    assert captured["auth"] == "Bearer eyJ-fake"
    await client.aclose()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/adapters/test_hardcover.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Write `lacuna/adapters/hardcover.py`**

```python
# lacuna/adapters/hardcover.py
from __future__ import annotations

import httpx
from pydantic import BaseModel

from lacuna.adapters._http import RateLimiter, USER_AGENT, request_with_backoff
from lacuna.schemas.sources import HardcoverReview

ENDPOINT = "https://api.hardcover.app/v1/graphql"

_BOOK_BY_TITLE = """
query BookByTitle($q: String!) {
  books(where: {title: {_ilike: $q}}, limit: 1) {
    id
    title
    reviews { id rating body user_id created_at }
  }
}
"""


class HardcoverBook(BaseModel):
    id: int
    title: str
    reviews: list[HardcoverReview] = []


class HardcoverClient:
    def __init__(self, token: str, *, timeout: float = 30.0):
        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers={"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT},
        )
        self._limiter = RateLimiter(per_minute=60)

    async def _query(self, query: str, variables: dict) -> dict:
        resp = await request_with_backoff(
            self._client, "POST", ENDPOINT,
            json={"query": query, "variables": variables},
            limiter=self._limiter,
        )
        payload = resp.json()
        if "errors" in payload:
            raise RuntimeError(f"Hardcover GraphQL error: {payload['errors']}")
        return payload["data"]

    async def fetch_book_by_title(self, title: str) -> HardcoverBook | None:
        data = await self._query(_BOOK_BY_TITLE, {"q": f"%{title}%"})
        books = data.get("books") or []
        return HardcoverBook.model_validate(books[0]) if books else None

    async def aclose(self) -> None:
        await self._client.aclose()
```

> **Flag (CLAUDE.md §2):** the exact GraphQL field names (`books`, `reviews`, `user_id`, `created_at`) are Hardcover's published schema as of the PRD, but Hardcover's schema is the explicit subject of the **G0 gate**. If G0 reveals different field names, this query string is the one-file change point — do not propagate the assumption elsewhere.

- [ ] **Step 4: Run it to verify it passes**

Run: `uv run pytest tests/adapters/test_hardcover.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add lacuna/adapters/hardcover.py tests/adapters/test_hardcover.py
git commit -m "feat: Hardcover GraphQL adapter (60/min, Bearer, boundary-validated)"
```

---

### Task B4: Google Books adapter (`adapters/google_books.py`)

**Files:**
- Create: `lacuna/adapters/google_books.py`
- Test: `tests/adapters/test_google_books.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/adapters/test_google_books.py
import httpx, respx
from lacuna.adapters.google_books import GoogleBooksClient

RECORDED = {"items": [
    {"volumeInfo": {"title": "Discipline Is Destiny", "categories": ["Self-Help"],
                    "averageRating": 4.2, "ratingsCount": 250}},
]}

@respx.mock
async def test_search_volumes_parses_and_extracts_ratings():
    respx.get(url__startswith="https://www.googleapis.com/books/v1/volumes").mock(
        return_value=httpx.Response(200, json=RECORDED))
    client = GoogleBooksClient(api_key="k")
    vols = await client.search("stoicism")
    assert vols[0].ratings_count == 250
    assert vols[0].categories == ["Self-Help"]
    await client.aclose()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/adapters/test_google_books.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Write `lacuna/adapters/google_books.py`**

```python
# lacuna/adapters/google_books.py
from __future__ import annotations

import httpx

from lacuna.adapters._http import RateLimiter, request_with_backoff
from lacuna.schemas.sources import GoogleVolume

BASE = "https://www.googleapis.com/books/v1/volumes"


class GoogleBooksClient:
    def __init__(self, api_key: str):
        self._client = httpx.AsyncClient(timeout=20.0)
        self._key = api_key
        self._limiter = RateLimiter(per_minute=60)  # well under ~1000/day

    async def search(self, query: str, *, max_results: int = 20) -> list[GoogleVolume]:
        resp = await request_with_backoff(
            self._client, "GET", BASE,
            params={"q": query, "maxResults": max_results, "key": self._key},
            limiter=self._limiter,
        )
        items = resp.json().get("items", [])
        return [GoogleVolume.model_validate(it) for it in items]

    async def aclose(self) -> None:
        await self._client.aclose()
```

- [ ] **Step 4: Run it to verify it passes**

Run: `uv run pytest tests/adapters/test_google_books.py -v`
Expected: passed.

- [ ] **Step 5: Commit**

```bash
git add lacuna/adapters/google_books.py tests/adapters/test_google_books.py
git commit -m "feat: Google Books adapter (ratings + BISAC-anchor categories)"
```

---

### Task B5: NYT Books adapter (`adapters/nyt.py`)

**Files:**
- Create: `lacuna/adapters/nyt.py`
- Test: `tests/adapters/test_nyt.py`

> NYT 10/min → ~6s spacing; limiter `per_minute=10`.

- [ ] **Step 1: Write the failing test**

```python
# tests/adapters/test_nyt.py
import httpx, respx
from lacuna.adapters.nyt import NytClient

RECORDED = {"results": {"books": [
    {"title": "ATOMIC HABITS", "weeks_on_list": 250, "rank": 1},
    {"title": "THE LET THEM THEORY", "weeks_on_list": 5, "rank": 2},
]}}

@respx.mock
async def test_list_bestsellers_parses():
    respx.get(url__startswith="https://api.nytimes.com/svc/books/v3/lists/current").mock(
        return_value=httpx.Response(200, json=RECORDED))
    client = NytClient(api_key="k")
    rows = await client.current_list("advice-how-to-and-miscellaneous")
    assert rows[0].title == "ATOMIC HABITS" and rows[0].weeks_on_list == 250
    await client.aclose()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/adapters/test_nyt.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Write `lacuna/adapters/nyt.py`**

```python
# lacuna/adapters/nyt.py
from __future__ import annotations

import httpx

from lacuna.adapters._http import RateLimiter, request_with_backoff
from lacuna.schemas.sources import NytBestseller

BASE = "https://api.nytimes.com/svc/books/v3/lists/current"


class NytClient:
    def __init__(self, api_key: str):
        self._client = httpx.AsyncClient(timeout=20.0)
        self._key = api_key
        self._limiter = RateLimiter(per_minute=10)  # PRD §4

    async def current_list(self, list_name: str) -> list[NytBestseller]:
        resp = await request_with_backoff(
            self._client, "GET", f"{BASE}/{list_name}.json",
            params={"api-key": self._key}, limiter=self._limiter,
        )
        books = resp.json().get("results", {}).get("books", [])
        return [NytBestseller.model_validate(b) for b in books]

    async def aclose(self) -> None:
        await self._client.aclose()
```

- [ ] **Step 4: Run it to verify it passes**

Run: `uv run pytest tests/adapters/test_nyt.py -v`
Expected: passed.

- [ ] **Step 5: Commit**

```bash
git add lacuna/adapters/nyt.py tests/adapters/test_nyt.py
git commit -m "feat: NYT Books adapter (bestseller presence, 10/min)"
```

---

### Task B6: Open Library adapter (`adapters/open_library.py`)

**Files:**
- Create: `lacuna/adapters/open_library.py`
- Test: `tests/adapters/test_open_library.py`

> Provides subject title counts + recency (for the time-skew guard's `recent_title_count`).

- [ ] **Step 1: Write the failing test**

```python
# tests/adapters/test_open_library.py
import httpx, respx
from lacuna.adapters.open_library import OpenLibraryClient

RECORDED = {"numFound": 2, "docs": [
    {"title": "Stoic Daily", "first_publish_year": 2024, "edition_count": 3},
    {"title": "On Discipline", "first_publish_year": 2018, "edition_count": 1},
]}

@respx.mock
async def test_subject_search_counts_recent_titles():
    respx.get(url__startswith="https://openlibrary.org/search.json").mock(
        return_value=httpx.Response(200, json=RECORDED))
    client = OpenLibraryClient()
    result = await client.subject_search("stoicism", cutoff_year=2023)
    assert result.title_count == 2
    assert result.recent_title_count == 1   # only the 2024 title is post-cutoff
    await client.aclose()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/adapters/test_open_library.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Write `lacuna/adapters/open_library.py`**

```python
# lacuna/adapters/open_library.py
from __future__ import annotations

import httpx
from pydantic import BaseModel

from lacuna.adapters._http import RateLimiter, request_with_backoff
from lacuna.schemas.sources import OpenLibraryDoc

BASE = "https://openlibrary.org/search.json"


class SupplyResult(BaseModel):
    title_count: int
    recent_title_count: int


class OpenLibraryClient:
    def __init__(self):
        self._client = httpx.AsyncClient(timeout=30.0)
        self._limiter = RateLimiter(per_minute=60)  # be polite

    async def subject_search(self, subject: str, *, cutoff_year: int = 2023,
                             limit: int = 100) -> SupplyResult:
        resp = await request_with_backoff(
            self._client, "GET", BASE,
            params={"q": f"subject:{subject}", "limit": limit,
                    "fields": "title,first_publish_year,edition_count"},
            limiter=self._limiter,
        )
        payload = resp.json()
        docs = [OpenLibraryDoc.model_validate(d) for d in payload.get("docs", [])]
        recent = sum(1 for d in docs if (d.first_publish_year or 0) > cutoff_year)
        return SupplyResult(title_count=payload.get("numFound", len(docs)),
                            recent_title_count=recent)

    async def aclose(self) -> None:
        await self._client.aclose()
```

- [ ] **Step 4: Run it to verify it passes**

Run: `uv run pytest tests/adapters/test_open_library.py -v`
Expected: passed.

- [ ] **Step 5: Commit**

```bash
git add lacuna/adapters/open_library.py tests/adapters/test_open_library.py
git commit -m "feat: Open Library adapter (supply counts + post-cutoff recency)"
```

---

### Task B7: Amazon corpus adapter (`adapters/corpus.py`)

**Files:**
- Create: `lacuna/adapters/corpus.py`
- Test: `tests/adapters/test_corpus.py`

> Streams HF parquet configs with the pinned revision; never full-download, never commit text (PRD §4, §6.2). Validates each row through `CorpusReview`.

- [ ] **Step 1: Write the failing test** (inject a fake iterable so no network/download in the unit test)

```python
# tests/adapters/test_corpus.py
from lacuna.adapters.corpus import iter_reviews, CORPUS_NAME

FAKE_ROWS = [
    {"asin": "B1", "parent_asin": "P1", "rating": 2.0, "title": "meh",
     "text": "examples are outdated", "helpful_vote": 9, "timestamp": 1_600_000_000_000, "user_id": "u1"},
    {"asin": "B2", "parent_asin": "P1", "rating": 5.0, "title": "great",
     "text": "loved it", "helpful_vote": 0, "timestamp": 1_600_000_000_000, "user_id": "u2"},
]

def test_iter_reviews_validates_and_yields():
    out = list(iter_reviews(_source=iter(FAKE_ROWS)))
    assert len(out) == 2
    assert out[0].asin == "B1" and out[0].helpful_vote == 9
    assert out[0].review_date is not None

def test_corpus_name_is_mcauley():
    assert CORPUS_NAME == "McAuley-Lab/Amazon-Reviews-2023"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/adapters/test_corpus.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Write `lacuna/adapters/corpus.py`**

```python
# lacuna/adapters/corpus.py
"""McAuley Amazon Reviews 2023 streaming adapter (PRD §4/§6).
Loads raw parquet configs with the pinned revision; streaming only; raw text
never written to the repo."""
from __future__ import annotations

from collections.abc import Iterable, Iterator

from lacuna.config import load_advanced
from lacuna.schemas.sources import CorpusReview

CORPUS_NAME = "McAuley-Lab/Amazon-Reviews-2023"
REVIEW_CONFIG = "raw_review_Books"
META_CONFIG = "raw_meta_Books"


def _pinned_revision() -> str:
    rev = load_advanced().get("dataset", {}).get("amazon_reviews", {}).get("revision")
    if not rev or rev == "<resolved-at-build>":
        raise RuntimeError("dataset revision not pinned — run scripts/pin_revisions.py (PRD §15)")
    return rev


def _hf_stream(config: str) -> Iterator[dict]:
    from datasets import load_dataset
    ds = load_dataset(
        CORPUS_NAME, config, split="full",
        streaming=True, revision=_pinned_revision(),
    )
    yield from ds


def iter_reviews(_source: Iterable[dict] | None = None) -> Iterator[CorpusReview]:
    """Yield validated reviews. `_source` injectable for tests; defaults to HF stream."""
    source = _source if _source is not None else _hf_stream(REVIEW_CONFIG)
    for row in source:
        yield CorpusReview.model_validate(row)


def iter_meta(_source: Iterable[dict] | None = None) -> Iterator[dict]:
    """Yield raw metadata rows (parsed into editions in Workstream C)."""
    source = _source if _source is not None else _hf_stream(META_CONFIG)
    yield from source
```

- [ ] **Step 4: Run it to verify it passes**

Run: `uv run pytest tests/adapters/test_corpus.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add lacuna/adapters/corpus.py tests/adapters/test_corpus.py
git commit -m "feat: McAuley Amazon corpus streaming adapter (pinned revision, validated)"
```

---

### Task B8: Full adapter suite green + no-leak check

- [ ] **Step 1: Run the whole adapter test suite**

Run: `uv run pytest tests/adapters tests/test_schemas.py -v`
Expected: all passed.

- [ ] **Step 2: Confirm no raw-corpus file was written anywhere**

Run: `git status --porcelain` and confirm no `.parquet`/`.jsonl`/`data/` paths are staged or present (they are git-ignored from A0). Expected: clean except plan/source files.

- [ ] **Step 3: Commit (suite checkpoint)**

```bash
git add -A
git commit -m "test: adapter suite green; no raw corpus committed"
```

---

## Self-review (against PRD)

- **§4 sources** — all five adapters present (Hardcover, NYT, Google Books, Open Library, corpus); Reddit absent. ✓
- **Rate/retry** — shared backoff honors `Retry-After`, jitter, RETRY_STATUS; per-source limiters (Hardcover 60, NYT 10). ✓
- **Boundary validation** — every adapter returns pydantic models; drift test asserts fail-loud. ✓
- **§6.2 streaming** — corpus uses `streaming=True`, pinned revision, no download to repo; `data/`/`*.parquet` git-ignored. ✓
- **Hardcover specifics** — Bearer without double prefix (test), 30s timeout, descriptive UA, 60/min. ✓
- **Type consistency** — `request_with_backoff`, `RateLimiter`, `HardcoverClient.fetch_book_by_title`, `CorpusReview`, `SupplyResult` names reused consistently into G0/C/E/G. ✓
- **Placeholder scan** — complete code + recorded responses in every contract test; no TODO/TBD. ✓

**Blocks cleared for:** G0 (Hardcover adapter ready) → then C, E, G.
