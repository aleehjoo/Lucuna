import os
import pytest

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"),
                                reason="DATABASE_URL not set")


async def test_create_list_get_delete_project(client):
    body = {"name": "Test Niche — API", "target_bisac": ["COM051000"],
            "subject_filter": {"keywords": ["python"]}, "config": {}}
    created = (await client.post("/projects", json=body)).json()
    pid = created["id"]
    assert created["name"] == body["name"]
    assert created["seeded"] is False
    assert created["work_count"] == 0

    listed = (await client.get("/projects")).json()
    assert any(p["id"] == pid for p in listed)

    got = (await client.get(f"/projects/{pid}")).json()
    assert got["id"] == pid

    # PUT — persist an intent knob into config (Settings surface)
    updated = (await client.put(f"/projects/{pid}",
                                json={"config": {"timely_evergreen": 0.7}})).json()
    assert updated["id"] == pid
    assert updated["config"] == {"timely_evergreen": 0.7}
    refetched = (await client.get(f"/projects/{pid}")).json()
    assert refetched["config"] == {"timely_evergreen": 0.7}  # config round-trips and is surfaced in ProjectOut

    assert (await client.delete(f"/projects/{pid}")).status_code == 204
    assert (await client.get(f"/projects/{pid}")).status_code == 404
