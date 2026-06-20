import os
import pytest

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"),
                                reason="DATABASE_URL not set")


async def test_export_json_returns_pack(client):
    projs = (await client.get("/projects")).json()
    seeded = [p for p in projs if p["seeded"]]
    if not seeded:
        pytest.skip("no seeded project")
    pid = seeded[0]["id"]
    resp = await client.get(f"/projects/{pid}/export", params={"format": "json"})
    assert resp.status_code == 200
    pack = resp.json()
    assert "candidates" in pack
    assert "known_limitations" in pack
