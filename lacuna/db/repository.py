# lacuna/db/repository.py
"""Async persistence for the seed pipeline (PRD §5/§6). Writes a SeedPlan to
Supabase in one transaction and records the analysis_run. Only structured rows
reach the DB — no raw text is sent to any external service (PRD §7).

`--rebuild` semantics: a full recompute deletes the project's existing works
(FK ON DELETE CASCADE clears editions/reviews/aspect_clusters) before reinserting.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from lacuna.db.models import AnalysisRun, AspectCluster, Edition, Project, Review, Work


async def _get_or_create_project(session, *, name: str, target_bisac: list[str],
                                 subject_filter: dict, config: dict) -> Project:
    proj = (await session.execute(select(Project).where(Project.name == name))).scalar_one_or_none()
    if proj is None:
        proj = Project(name=name, target_bisac=target_bisac,
                       subject_filter=subject_filter, config=config)
        session.add(proj)
        await session.flush()
    return proj


async def persist_seed_plan(
    sessionmaker: async_sessionmaker,
    plan,
    *,
    project_name: str,
    target_bisac: list[str],
    subject_filter: dict,
    config: dict,
    rebuild: bool = True,
) -> dict:
    """Persist a SeedPlan. Returns counts. Inserts in FK order (project → works →
    editions → aspect_clusters → reviews) using flush() to resolve server-side UUIDs."""
    async with sessionmaker() as session:
        async with session.begin():
            proj = await _get_or_create_project(
                session, name=project_name, target_bisac=target_bisac,
                subject_filter=subject_filter, config=config)

            if rebuild:
                await session.execute(delete(Work).where(Work.project_id == proj.id))
                await session.flush()

            # Works
            work_id_by_key: dict[str, object] = {}
            for w in plan.works:
                obj = Work(
                    project_id=proj.id, normalized_key=w.normalized_key,
                    norm_version=w.norm_version, title=w.title, author=w.author,
                    edition_count=len(w.edition_asins),
                    agg_rating_avg=w.rating_avg, agg_rating_count=w.rating_count,
                )
                session.add(obj)
                work_id_by_key[w.normalized_key] = obj
            await session.flush()
            work_id_by_key = {k: v.id for k, v in work_id_by_key.items()}

            # Editions
            edition_id_by_asin: dict[str, object] = {}
            for e in plan.editions:
                obj = Edition(
                    work_id=work_id_by_key[e.work_key], project_id=proj.id,
                    asin=e.asin, parent_asin=e.parent_asin, isbn13=e.isbn13,
                    isbn10=e.isbn10, format=e.format, price_cents=e.price_cents,
                )
                session.add(obj)
                edition_id_by_asin[e.asin] = obj
            await session.flush()
            edition_id_by_asin = {k: v.id for k, v in edition_id_by_asin.items()}

            # Aspect clusters -> id keyed by the plan's global local_id. Clusters are
            # niche-level (work_id=None, bisac_code set) when pooled across the niche
            # (PRD §6.6); a per-work cluster (work_key set) maps to its work_id.
            cluster_id_by_local: dict[int, object] = {}
            for c in plan.clusters:
                obj = AspectCluster(
                    project_id=proj.id,
                    work_id=work_id_by_key[c.work_key] if c.work_key else None,
                    bisac_code=c.bisac_code,
                    label=c.label, member_count=c.member_count,
                    reviewer_count=c.reviewer_count, helpful_weight=c.helpful_weight,
                    platforms=c.platforms, cross_platform=False,
                    representative=c.representative,
                )
                session.add(obj)
                cluster_id_by_local[c.local_id] = obj
            await session.flush()
            cluster_id_by_local = {k: v.id for k, v in cluster_id_by_local.items()}

            # Reviews — idempotent upsert (PRD §6.1.7). Dedupe within the batch
            # (the corpus can carry the same review twice → identical external_id)
            # then ON CONFLICT DO NOTHING so a re-seed never crashes on a key that
            # already exists. Uniqueness is per-project (migration 0002).
            seen_external: set[str] = set()
            review_rows: list[dict] = []
            for r in plan.reviews:
                if r.external_id in seen_external:
                    continue
                seen_external.add(r.external_id)
                cid = cluster_id_by_local.get(r.cluster_local_id) \
                    if r.cluster_local_id is not None else None
                review_rows.append(dict(
                    work_id=work_id_by_key[r.work_key], project_id=proj.id,
                    edition_id=edition_id_by_asin.get(r.edition_asin),
                    platform="amazon_corpus", external_id=r.external_id,
                    rating=r.rating, helpful_votes=r.helpful_votes,
                    review_date=r.review_date, text=r.text,
                    embedding=r.embedding, aspect_cluster_id=cid,
                    sentiment=r.sentiment, processed=True,
                ))
            if review_rows:
                await session.execute(
                    pg_insert(Review).values(review_rows).on_conflict_do_nothing(
                        index_elements=["project_id", "platform", "external_id"]))
        # transaction committed on exit
        return {"project_id": str(proj.id), **plan.counts}


async def record_run(sessionmaker: async_sessionmaker, *, mode: str, target: str | None,
                     sources_used: list[str], status: str, counts: dict,
                     project_id=None, error_detail: str | None = None) -> int:
    async with sessionmaker() as session:
        async with session.begin():
            run = AnalysisRun(
                project_id=project_id, mode=mode, target=target,
                sources_used=sources_used, status=status, counts=counts,
                finished_at=dt.datetime.now(dt.timezone.utc), error_detail=error_detail,
            )
            session.add(run)
            await session.flush()
            return run.id
