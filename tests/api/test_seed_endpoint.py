# tests/api/test_seed_endpoint.py
"""POST /projects/{id}/seed must return a job id immediately WITHOUT running a
real (hour-long) seed — subprocess.Popen is monkeypatched so no child process is
actually spawned (Frontend PRD §3.1/§13.5: seed runs as a separate subprocess,
never inside the API event loop)."""
from __future__ import annotations

import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"),
                                reason="DATABASE_URL not set")


async def test_seed_returns_job_id_without_blocking(client, monkeypatch):
    import api.routers.seed as seed_router

    spawned = {}

    class _FakePopen:
        def __init__(self, args, **kw):
            spawned["args"] = args

    monkeypatch.setattr(seed_router.subprocess, "Popen", _FakePopen)

    projs = (await client.get("/projects")).json()
    pid = projs[0]["id"] if projs else None
    if pid is None:
        pytest.skip("no project")

    resp = await client.post(f"/projects/{pid}/seed", json={"max_works": 25})
    assert resp.status_code == 200
    body = resp.json()
    assert uuid.UUID(body["job_id"])
    assert "seed-job" in spawned["args"]
    assert str(body["job_id"]) in spawned["args"]
