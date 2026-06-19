# api/jobs.py
"""Jobs service (Frontend PRD §13.6): the one async-status surface the UI polls.
Thin CRUD over the `jobs` table; engine math lives elsewhere."""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from lacuna.db.models import Job


def _row_to_dict(j: Job) -> dict:
    return {
        "id": str(j.id), "project_id": str(j.project_id) if j.project_id else None,
        "kind": j.kind, "status": j.status, "progress_pct": float(j.progress_pct),
        "step": j.step, "counts": j.counts, "result_ref": j.result_ref,
        "error_detail": j.error_detail,
        "created_at": j.created_at.isoformat() if j.created_at else None,
        "updated_at": j.updated_at.isoformat() if j.updated_at else None,
    }


async def create_job(sm: async_sessionmaker, *, kind: str,
                     project_id: uuid.UUID | None) -> uuid.UUID:
    async with sm() as session:
        async with session.begin():
            job = Job(kind=kind, project_id=project_id, status="queued")
            session.add(job)
            await session.flush()
            return job.id


async def get_job(sm: async_sessionmaker, job_id: uuid.UUID) -> dict | None:
    async with sm() as session:
        job = (await session.execute(select(Job).where(Job.id == job_id))).scalar_one_or_none()
        return _row_to_dict(job) if job else None


async def update_job(sm: async_sessionmaker, job_id: uuid.UUID, *, status=None,
                     progress_pct=None, step=None, counts=None,
                     result_ref=None, error_detail=None) -> None:
    async with sm() as session:
        async with session.begin():
            job = (await session.execute(select(Job).where(Job.id == job_id))).scalar_one_or_none()
            if job is None:
                return
            if status is not None: job.status = status
            if progress_pct is not None: job.progress_pct = progress_pct
            if step is not None: job.step = step
            if counts is not None: job.counts = counts
            if result_ref is not None: job.result_ref = result_ref
            if error_detail is not None: job.error_detail = error_detail
            job.updated_at = dt.datetime.now(dt.timezone.utc)


async def list_jobs(sm: async_sessionmaker, project_id: uuid.UUID, *, limit: int = 20) -> list[dict]:
    async with sm() as session:
        rows = (await session.execute(
            select(Job).where(Job.project_id == project_id)
            .order_by(Job.created_at.desc()).limit(limit))).scalars().all()
        return [_row_to_dict(r) for r in rows]
