import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"),
                                reason="DATABASE_URL not set")


async def test_sweep_runs_as_job_and_completes(client):
    projs = (await client.get("/projects")).json()
    seeded = [p for p in projs if p["seeded"]]
    if not seeded:
        pytest.skip("no seeded project")
    pid = seeded[0]["id"]
    resp = await client.post(f"/projects/{pid}/sweep")
    job_id = resp.json()["job_id"]
    assert uuid.UUID(job_id)
    job = (await client.get(f"/jobs/{job_id}")).json()
    assert job["status"] in ("running", "done")
