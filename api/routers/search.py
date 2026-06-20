# api/routers/search.py
"""Live single-title search (Frontend PRD §3.2) as a job. Hardcover ONLY — never
the corpus (CLAUDE.md §3 / PRD §1.2 HARD RULE). Wraps Task 10's `analyze_live`,
running the heavy NLP off the event loop with the WARM runtime's models (no
per-request reload, §13.4). The UI polls GET /jobs/{id} for status."""
from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from api import jobs as jobs_svc
from api.deps import get_runtime, get_sessionmaker
from api.schemas import SearchRequest
from lacuna.adapters.hardcover import HardcoverClient
from lacuna.aggregation.cross_platform import AspectClusterIn
from lacuna.config import get_settings
from lacuna.db.models import AspectCluster, Work
from lacuna.pipeline.live_single_title import analyze_live
from lacuna.seed.normalization import normalized_key

router = APIRouter(prefix="/projects/{project_id}", tags=["search"])


def _hardcover_token() -> str | None:
    return get_settings().hardcover_api_token


async def _seeded_clusters_for(sm, project_id: uuid.UUID, title: str) -> list[AspectClusterIn]:
    """If a seeded work in THIS project matches this title, return its clusters as
    merge inputs; else [] (fresh-only). Matching reuses the seed's OWN
    `normalized_key(title, author)` (lacuna/seed/normalization.py) — the exact
    function the seed used to build `Work.normalized_key` (see orchestrator.py).
    The search request carries no author, so we normalize the search title against
    each candidate work's OWN stored author (defensive: an exact normalized_key
    string match without an author is unreliable, since normalized_key embeds the
    author). This still correctly resolves the common case (single edition/author
    per normalized title in a project) and degrades safely to [] otherwise."""
    async with sm() as session:
        works = (await session.execute(
            select(Work).where(Work.project_id == project_id))).scalars().all()
        match = next(
            (w for w in works if normalized_key(title, w.author) == w.normalized_key),
            None,
        )
        if match is None:
            return []
        cls = (await session.execute(
            select(AspectCluster).where(AspectCluster.work_id == match.id))).scalars().all()
        return [AspectClusterIn(label=c.label, platform=(c.platforms[0] if c.platforms else "amazon_corpus"),
                                reviewer_count=c.reviewer_count, helpful_weight=float(c.helpful_weight or 0.0),
                                member_count=c.member_count) for c in cls]


@router.post("/search")
async def start_search(project_id: uuid.UUID, body: SearchRequest,
                       sm=Depends(get_sessionmaker), runtime=Depends(get_runtime)):
    """Live single-title search (Frontend PRD §3.2). Hardcover ONLY — never the corpus
    (§1.2). Runs as a job for consistent UX; the heavy NLP runs off the event loop
    with the WARM models."""
    if not body.title and not body.isbn:
        raise HTTPException(status_code=422, detail="title or isbn required")
    token = _hardcover_token()
    if not token:
        raise HTTPException(status_code=503, detail="HARDCOVER_API_TOKEN not configured on the backend")

    job_id = await jobs_svc.create_job(sm, kind="live_search", project_id=project_id)
    title = body.title or body.isbn
    seeded = await _seeded_clusters_for(sm, project_id, title)

    await jobs_svc.update_job(sm, job_id, status="running", progress_pct=5, step="resolving")
    client = HardcoverClient(token=token)
    try:
        def _run():
            return asyncio.run(analyze_live(
                title=title, hardcover=client, embedder=runtime.embedder,
                labeler=runtime.labeler, seeded_clusters=seeded or None))
        result = await run_in_threadpool(_run)
        await jobs_svc.update_job(
            sm, job_id, status="done", progress_pct=100,
            counts={"review_count": result["review_count"], "fresh_only": result["fresh_only"],
                    "agreement_pct": result["agreement_pct"], "clusters": result["clusters"],
                    "pack": result["pack"]})
    except Exception as exc:  # noqa: BLE001
        await jobs_svc.update_job(sm, job_id, status="error", error_detail=str(exc))
    finally:
        await client.aclose()

    return {"job_id": str(job_id)}
