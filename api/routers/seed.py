# api/routers/seed.py
"""Batch seed launcher (Frontend PRD §3.1/§13.5): the seed is CPU-heavy and can
run ~1 hour, so it MUST run as a separate subprocess of the existing CLI — never
inside the API process/event loop. This endpoint only creates the jobs row and
spawns the subprocess; it returns immediately."""
from __future__ import annotations

import subprocess
import sys
import uuid

from fastapi import APIRouter, Depends

from api import jobs as jobs_svc
from api.deps import get_sessionmaker
from api.schemas import SeedRequest
from lacuna.config import ROOT

router = APIRouter(prefix="/projects/{project_id}", tags=["seed"])


@router.post("/seed")
async def start_seed(project_id: uuid.UUID, body: SeedRequest, sm=Depends(get_sessionmaker)):
    """Start a batch seed as a SEPARATE SUBPROCESS (Frontend PRD §3.1/§13.5). Returns
    a job id immediately; progress lands in the jobs row via `lacuna seed-job`. Not
    resumable (matches the engine): a crash -> status='error' and the operator
    re-runs."""
    job_id = await jobs_svc.create_job(sm, kind="seed", project_id=project_id)
    try:
        subprocess.Popen(
            [sys.executable, "-m", "app.cli", "seed-job", str(job_id),
             "--max-works", str(body.max_works),
             "--meta-limit", str(body.meta_limit),
             "--review-limit", str(body.review_limit)],
            cwd=str(ROOT),
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
    except Exception as exc:  # noqa: BLE001 — record then let the UI surface the error
        await jobs_svc.update_job(sm, job_id, status="error",
                                   error_detail=f"failed to launch seed subprocess: {exc}")
    return {"job_id": str(job_id)}
