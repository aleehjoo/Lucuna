# api/routers/sweep.py
from __future__ import annotations

import asyncio
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from starlette.concurrency import run_in_threadpool

from api.deps import get_sessionmaker
from api import jobs as jobs_svc
from lacuna.pipeline.distill import distill_score_export

router = APIRouter(prefix="/projects/{project_id}", tags=["sweep"])


def _run_sweep_sync(job_id: uuid.UUID, project_id: uuid.UUID) -> None:
    """Runs OFF the event loop (via run_in_threadpool) in a fire-and-forget task.
    Builds its OWN sessionmaker/engine — the request that scheduled this has
    already returned, so its session/connection must not be reused here. Drives
    the distiller via its own asyncio event loop (this thread has none)."""
    from lacuna.db.session import build_engine, build_sessionmaker

    engine = build_engine()
    job_sm = build_sessionmaker(engine)
    try:
        try:
            with tempfile.TemporaryDirectory() as d:
                out = str(Path(d) / "pack.json")
                counts = asyncio.run(distill_score_export(
                    out=out, mode="category_sweep", project_id=str(project_id)))
            asyncio.run(jobs_svc.update_job(
                job_sm, job_id, status="done", progress_pct=100, counts=counts))
        except Exception as exc:  # noqa: BLE001
            asyncio.run(jobs_svc.update_job(
                job_sm, job_id, status="error", error_detail=str(exc)))
    finally:
        asyncio.run(engine.dispose())


@router.post("/sweep")
async def start_sweep(request: Request, project_id: uuid.UUID, sm=Depends(get_sessionmaker)):
    """Category Sweep (Frontend PRD §11) as a fire-and-forget job. Corpus-only,
    $0 — reads seeded data + persists scores; no live source, no hour-long scan.
    Returns {job_id} immediately; the ~25s distiller run happens in the
    background, off the event loop. Results via GET /candidates; progress via
    GET /jobs/{job_id} (the single source of truth — UI polls it)."""
    job_id = await jobs_svc.create_job(sm, kind="sweep", project_id=project_id)
    await jobs_svc.update_job(sm, job_id, status="running", progress_pct=10, step="scoring")

    async def _background() -> None:
        await run_in_threadpool(_run_sweep_sync, job_id, project_id)

    tasks: set = getattr(request.app.state, "background_tasks", None)
    if tasks is None:
        tasks = set()
        request.app.state.background_tasks = tasks
    task = asyncio.create_task(_background())
    tasks.add(task)
    task.add_done_callback(tasks.discard)

    return {"job_id": str(job_id)}
