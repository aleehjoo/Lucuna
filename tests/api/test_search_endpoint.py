import asyncio
import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"),
                                reason="DATABASE_URL not set")


async def test_search_creates_job_and_runs_live(client, monkeypatch):
    import api.routers.search as search_router

    class _FakeReview:
        def __init__(self, rating, body):
            self.rating = rating; self.body = body; self.created_at = None

    class _FakeBook:
        id = 1; title = "Mocked"
        reviews = [_FakeReview(2, "outdated examples"), _FakeReview(1, "dated content here")]

    class _FakeHC:
        def __init__(self, *a, **k): pass
        async def fetch_book_by_title(self, title, *, review_limit=50): return _FakeBook()
        async def aclose(self): pass

    monkeypatch.setattr(search_router, "HardcoverClient", _FakeHC)
    monkeypatch.setattr(search_router, "_hardcover_token", lambda: "fake-token")

    projs = (await client.get("/projects")).json()
    pid = projs[0]["id"] if projs else None
    if pid is None:
        pytest.skip("no project")
    resp = await client.post(f"/projects/{pid}/search", json={"title": "Mocked"})
    job_id = resp.json()["job_id"]
    assert uuid.UUID(job_id)

    # job should resolve to done with the live result (search is seconds)
    job = (await client.get(f"/jobs/{job_id}")).json()
    assert job["status"] in ("running", "done")

    # Poll until done: the router's counts dict must carry `title` (the
    # SearchResult heading) and `not_found` (drives the unresolved-title
    # EmptyState) straight through from analyze_live()'s result — regression
    # test for the bug where the router hand-listed keys and dropped both.
    for _ in range(50):
        job = (await client.get(f"/jobs/{job_id}")).json()
        if job["status"] == "done":
            break
        await asyncio.sleep(0.1)
    assert job["status"] == "done"
    assert job["counts"]["title"] == "Mocked"
    assert "not_found" in job["counts"]
    assert job["counts"]["not_found"] is False


async def test_search_requires_title_or_isbn(client, monkeypatch):
    import api.routers.search as search_router
    monkeypatch.setattr(search_router, "_hardcover_token", lambda: "fake-token")

    projs = (await client.get("/projects")).json()
    pid = projs[0]["id"] if projs else None
    if pid is None:
        pytest.skip("no project")
    resp = await client.post(f"/projects/{pid}/search", json={})
    assert resp.status_code == 422


async def test_search_503_when_token_missing(client, monkeypatch):
    import api.routers.search as search_router
    monkeypatch.setattr(search_router, "_hardcover_token", lambda: None)

    projs = (await client.get("/projects")).json()
    pid = projs[0]["id"] if projs else None
    if pid is None:
        pytest.skip("no project")
    resp = await client.post(f"/projects/{pid}/search", json={"title": "Mocked"})
    assert resp.status_code == 503
