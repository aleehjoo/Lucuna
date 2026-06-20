import os
import pytest

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"),
                                reason="DATABASE_URL not set")


async def _seeded_project_id(client):
    projs = (await client.get("/projects")).json()
    seeded = [p for p in projs if p["seeded"]]
    return seeded[0]["id"] if seeded else None


async def test_works_and_clusters_read(client):
    pid = await _seeded_project_id(client)
    if pid is None:
        pytest.skip("no seeded project in this DB")
    works = (await client.get(f"/projects/{pid}/works")).json()
    assert isinstance(works, list)
    if works:
        wid = works[0]["id"]
        detail = (await client.get(f"/projects/{pid}/works/{wid}")).json()
        assert detail["id"] == wid
        assert "clusters" in detail


async def test_candidates_ranked_desc(client):
    pid = await _seeded_project_id(client)
    if pid is None:
        pytest.skip("no seeded project in this DB")
    cands = (await client.get(f"/projects/{pid}/candidates")).json()
    gaps = [c["gap_score"] for c in cands]
    assert gaps == sorted(gaps, reverse=True)
