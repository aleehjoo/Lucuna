import os
import pytest

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"),
                                reason="DATABASE_URL not set")


async def test_get_job_404_for_unknown(client):
    import uuid
    resp = await client.get(f"/jobs/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_cancel_marks_running_job_cancelled(client):
    from lacuna.db.session import build_sessionmaker
    from api import jobs as jobs_svc
    sm = build_sessionmaker()
    jid = await jobs_svc.create_job(sm, kind="live_search", project_id=None)
    await jobs_svc.update_job(sm, jid, status="running", progress_pct=20)
    resp = await client.post(f"/jobs/{jid}/cancel")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "error" and body["error_detail"] == "cancelled"
