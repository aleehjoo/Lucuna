# api/routers/projects.py
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select

from api.deps import get_sessionmaker
from api.schemas import ProjectCreate, ProjectOut, ProjectUpdate
from lacuna.db.models import AspectCluster, Project, Work

router = APIRouter(prefix="/projects", tags=["projects"])


async def _project_out(session, p: Project) -> ProjectOut:
    wc = (await session.execute(
        select(func.count()).select_from(Work).where(Work.project_id == p.id))).scalar_one()
    cc = (await session.execute(
        select(func.count()).select_from(AspectCluster).where(AspectCluster.project_id == p.id))).scalar_one()
    return ProjectOut(
        id=str(p.id), name=p.name, target_bisac=list(p.target_bisac or []),
        subject_filter=p.subject_filter or {}, seeded=wc > 0,
        work_count=wc, cluster_count=cc,
        created_at=p.created_at.isoformat() if p.created_at else None)


@router.get("", response_model=list[ProjectOut])
async def list_projects(sm=Depends(get_sessionmaker)):
    async with sm() as session:
        projs = (await session.execute(select(Project).order_by(Project.created_at.desc()))).scalars().all()
        return [await _project_out(session, p) for p in projs]


@router.post("", response_model=ProjectOut, status_code=201)
async def create_project(body: ProjectCreate, sm=Depends(get_sessionmaker)):
    async with sm() as session:
        async with session.begin():
            p = Project(name=body.name, target_bisac=body.target_bisac,
                        subject_filter=body.subject_filter, config=body.config)
            session.add(p)
            await session.flush()
            return await _project_out(session, p)


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(project_id: uuid.UUID, sm=Depends(get_sessionmaker)):
    async with sm() as session:
        p = (await session.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
        if p is None:
            raise HTTPException(status_code=404, detail="project not found")
        return await _project_out(session, p)


@router.put("/{project_id}", response_model=ProjectOut)
async def update_project(project_id: uuid.UUID, body: ProjectUpdate, sm=Depends(get_sessionmaker)):
    """Partial update; powers Settings (intent knobs into config, Frontend PRD §10).
    Correctness knobs are never accepted here — the UI only sends intent knobs."""
    async with sm() as session:
        async with session.begin():
            p = (await session.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
            if p is None:
                raise HTTPException(status_code=404, detail="project not found")
            if body.name is not None: p.name = body.name
            if body.target_bisac is not None: p.target_bisac = body.target_bisac
            if body.subject_filter is not None: p.subject_filter = body.subject_filter
            if body.config is not None: p.config = body.config
            await session.flush()
            return await _project_out(session, p)


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: uuid.UUID, sm=Depends(get_sessionmaker)):
    async with sm() as session:
        async with session.begin():
            res = await session.execute(delete(Project).where(Project.id == project_id))
            if res.rowcount == 0:
                raise HTTPException(status_code=404, detail="project not found")
