# api/routers/reads.py
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select

from api.deps import get_sessionmaker
from lacuna.db.models import AspectCluster, Review, Score, Work

router = APIRouter(prefix="/projects/{project_id}", tags=["reads"])


def _cluster_dict(c: AspectCluster) -> dict:
    return {"id": c.id, "label": c.label, "representative": c.representative,
            "member_count": c.member_count, "reviewer_count": c.reviewer_count,
            "helpful_weight": float(c.helpful_weight or 0.0), "platforms": list(c.platforms or []),
            "cross_platform": bool(c.cross_platform), "work_id": str(c.work_id) if c.work_id else None,
            "bisac_code": c.bisac_code}


@router.get("/works")
async def list_works(project_id: uuid.UUID, sm=Depends(get_sessionmaker)):
    async with sm() as session:
        works = (await session.execute(
            select(Work).where(Work.project_id == project_id))).scalars().all()
        rc = dict((await session.execute(
            select(Review.work_id, func.count()).where(Review.project_id == project_id)
            .group_by(Review.work_id))).all())
        return [{"id": str(w.id), "title": w.title, "author": w.author,
                 "agg_rating_avg": float(w.agg_rating_avg) if w.agg_rating_avg is not None else None,
                 "agg_rating_count": w.agg_rating_count,
                 "review_count": rc.get(w.id, 0)} for w in works]


@router.get("/works/{work_id}")
async def work_detail(project_id: uuid.UUID, work_id: uuid.UUID, sm=Depends(get_sessionmaker)):
    async with sm() as session:
        w = (await session.execute(
            select(Work).where(Work.id == work_id, Work.project_id == project_id))).scalar_one_or_none()
        if w is None:
            raise HTTPException(status_code=404, detail="work not found")
        clusters = (await session.execute(
            select(AspectCluster).where(AspectCluster.work_id == work_id))).scalars().all()
        review_count = (await session.execute(
            select(func.count()).select_from(Review).where(Review.work_id == work_id))).scalar_one()
        return {"id": str(w.id), "title": w.title, "author": w.author,
                "agg_rating_avg": float(w.agg_rating_avg) if w.agg_rating_avg is not None else None,
                "agg_rating_count": w.agg_rating_count, "review_count": review_count,
                "clusters": [_cluster_dict(c) for c in clusters]}


@router.get("/clusters")
async def list_clusters(project_id: uuid.UUID, scope: str = Query("work"),
                        ref: str | None = None, sm=Depends(get_sessionmaker)):
    work_ref: uuid.UUID | None = None
    if scope != "bisac" and ref:
        try:
            work_ref = uuid.UUID(ref)
        except ValueError:
            raise HTTPException(status_code=422, detail="ref must be a valid UUID")
    async with sm() as session:
        stmt = select(AspectCluster).where(AspectCluster.project_id == project_id)
        if scope == "bisac":
            stmt = stmt.where(AspectCluster.work_id.is_(None))
            if ref:
                stmt = stmt.where(AspectCluster.bisac_code == ref)
        else:
            stmt = stmt.where(AspectCluster.work_id.is_not(None))
            if work_ref is not None:
                stmt = stmt.where(AspectCluster.work_id == work_ref)
        rows = (await session.execute(stmt)).scalars().all()
        return [_cluster_dict(c) for c in rows]


def _score_dict(s: Score) -> dict:
    return {"scope": s.scope, "ref_id": s.ref_id,
            "gap_score": float(s.gap_score) if s.gap_score is not None else 0.0,
            "demand_score": float(s.demand_score) if s.demand_score is not None else 0.0,
            "supply_scarcity": float(s.supply_scarcity) if s.supply_scarcity is not None else 0.0,
            "unmet_need": float(s.unmet_need) if s.unmet_need is not None else 0.0,
            "confidence": float(s.confidence), "sample_size": s.sample_size,
            "platforms_used": list(s.platforms_used or []),
            "incomplete": s.incomplete, "blind_spot": s.blind_spot,
            "recent_supply_surge": s.recent_supply_surge}


@router.get("/scores")
async def list_scores(project_id: uuid.UUID, sm=Depends(get_sessionmaker)):
    async with sm() as session:
        rows = (await session.execute(
            select(Score).where(Score.project_id == project_id))).scalars().all()
        return [_score_dict(s) for s in rows]


@router.get("/candidates")
async def list_candidates(project_id: uuid.UUID, sm=Depends(get_sessionmaker)):
    """Ranked candidates (gap_score desc), each joined to a human title. Work scope
    -> work title; bisac scope -> 'CODE — niche complaint clusters'."""
    async with sm() as session:
        scores = (await session.execute(
            select(Score).where(Score.project_id == project_id)
            .order_by(Score.gap_score.desc().nullslast()))).scalars().all()
        works = {str(w.id): w for w in (await session.execute(
            select(Work).where(Work.project_id == project_id))).scalars().all()}
        out = []
        for s in scores:
            d = _score_dict(s)
            if s.scope == "work":
                w = works.get(s.ref_id)
                d["title"] = w.title if w else s.ref_id
            else:
                code = s.ref_id.split(":", 1)[-1]
                d["title"] = f"{code} — niche complaint clusters"
            out.append(d)
        return out
