import os
import uuid

import pytest

from lacuna.db.session import build_sessionmaker
from api import jobs as jobs_svc

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set — jobs service DB test skipped",
)


async def test_job_lifecycle_create_update_get():
    sm = build_sessionmaker()
    jid = await jobs_svc.create_job(sm, kind="live_search", project_id=None)
    assert isinstance(jid, uuid.UUID)

    row = await jobs_svc.get_job(sm, jid)
    assert row["status"] == "queued"
    assert row["kind"] == "live_search"

    await jobs_svc.update_job(sm, jid, status="running", progress_pct=50, step="clustering")
    row = await jobs_svc.get_job(sm, jid)
    assert row["status"] == "running"
    assert float(row["progress_pct"]) == 50.0
    assert row["step"] == "clustering"

    await jobs_svc.update_job(sm, jid, status="done", progress_pct=100, result_ref="pack.json")
    row = await jobs_svc.get_job(sm, jid)
    assert row["status"] == "done"
    assert row["result_ref"] == "pack.json"
