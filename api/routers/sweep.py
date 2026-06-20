# api/routers/sweep.py
from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends
from starlette.concurrency import run_in_threadpool

from api.deps import get_sessionmaker
from api import jobs as jobs_svc
from lacuna.pipeline.distill import distill_score_export

router = APIRouter(prefix="/projects/{project_id}", tags=["sweep"])


@router.post("/sweep")
async def start_sweep(project_id: uuid.UUID, sm=Depends(get_sessionmaker)):
    """Category Sweep (Frontend PRD §11) as a job. Corpus-only, $0 — reads seeded
    data + persists scores; no live source, no hour-long scan. Runs off the event
    loop. Results via GET /candidates."""
    job_id = await jobs_svc.create_job(sm, kind="sweep", project_id=project_id)
    await jobs_svc.update_job(sm, job_id, status="running", progress_pct=10, step="scoring")

    def _run() -> dict:
        import asyncio
        with tempfile.TemporaryDirectory() as d:
            out = str(Path(d) / "pack.json")
            return asyncio.run(distill_score_export(
                out=out, mode="category_sweep", project_id=str(project_id)))

    try:
        counts = await run_in_threadpool(_run)
        await jobs_svc.update_job(sm, job_id, status="done", progress_pct=100, counts=counts)
    except Exception as exc:  # noqa: BLE001
        await jobs_svc.update_job(sm, job_id, status="error", error_detail=str(exc))
    return {"job_id": str(job_id)}
