import asyncio
import os
import time
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

    post_start = time.monotonic()
    resp = await client.post(f"/projects/{pid}/sweep")
    post_elapsed = time.monotonic() - post_start
    job_id = resp.json()["job_id"]
    assert uuid.UUID(job_id)
    # Fire-and-forget: the POST must return well before the ~25s distiller run
    # finishes, proving the HTTP response did not wait on it.
    assert post_elapsed < 10, (
        f"POST /sweep took {post_elapsed:.1f}s — looks like it blocked on the "
        "distiller run instead of returning immediately"
    )

    # Poll GET /jobs/{job_id} until it reaches a terminal state. This proves the
    # background path actually runs to completion, not just that POST returned.
    deadline = time.monotonic() + 90
    job = None
    while time.monotonic() < deadline:
        job = (await client.get(f"/jobs/{job_id}")).json()
        if job["status"] in ("done", "error"):
            break
        await asyncio.sleep(2)

    assert job is not None
    assert job["status"] == "done", f"job did not complete: {job}"
