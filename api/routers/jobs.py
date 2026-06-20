# api/routers/jobs.py
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_sessionmaker
from api.schemas import JobOut
from api import jobs as jobs_svc

router = APIRouter(tags=["jobs"])


@router.get("/jobs/{job_id}", response_model=JobOut)
async def get_job(job_id: uuid.UUID, sm=Depends(get_sessionmaker)):
    row = await jobs_svc.get_job(sm, job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="job not found")
    return row


@router.post("/jobs/{job_id}/cancel", response_model=JobOut)
async def cancel_job(job_id: uuid.UUID, sm=Depends(get_sessionmaker)):
    """Cancel a running job (Frontend PRD §11). The `jobs` CHECK constraint allows
    only queued/running/done/error (no schema change, §13.12), so cancellation is
    recorded as status='error' with error_detail='cancelled' — the UI renders that
    marker as 'Cancelled', not a failure. The UI stops polling on this terminal state.
    For live_search (seconds) this primarily halts UI polling + marks the row; the
    in-flight threadpool task is allowed to finish (no hard mid-NLP kill in v1)."""
    row = await jobs_svc.get_job(sm, job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="job not found")
    if row["status"] in ("done", "error"):
        return row  # already terminal — idempotent
    await jobs_svc.update_job(sm, job_id, status="error", error_detail="cancelled")
    return await jobs_svc.get_job(sm, job_id)


@router.get("/projects/{project_id}/jobs", response_model=list[JobOut])
async def list_project_jobs(project_id: uuid.UUID, sm=Depends(get_sessionmaker)):
    return await jobs_svc.list_jobs(sm, project_id)
