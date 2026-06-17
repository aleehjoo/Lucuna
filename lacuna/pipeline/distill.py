# lacuna/pipeline/distill.py
"""Corpus-only distill → score → export pipeline (PRD §10/§11/§12, $0 path).

Reads the seeded works + aspect_clusters from Supabase, builds cohort Candidates
(F), scores them, writes the `scores` table, and emits the Context Pack (H) as a
JSON + Markdown twin. Runs end-to-end with ANTHROPIC_API_KEY unset and no external
keys: demand/supply signals (NYT/Google/Hardcover/OpenLibrary) are absent here, so
those components are correctly WITHHELD and candidates are flagged incomplete —
the honest state for a corpus-only run. The fresh-pull single-title path lives in
single_title.analyze (needs a Hardcover token)."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from sqlalchemy import func, select

from lacuna.aggregation.cross_platform import AspectClusterIn, agreement_pct, merge_clusters
from lacuna.config import load_advanced, load_default
from lacuna.db.models import AspectCluster, Project, Review, Score, Work
from lacuna.db.session import build_sessionmaker
from lacuna.export.context_pack import Candidate as PackCandidate
from lacuna.export.context_pack import Complaint, build_pack, to_markdown
from lacuna.nlp.embeddings import Embedder
from lacuna.scoring.components import derive_components
from lacuna.scoring.gap_score import load_cfg, score_cohort


async def _load_project(session, name: str) -> Project | None:
    return (await session.execute(select(Project).where(Project.name == name))).scalar_one_or_none()


async def distill_score_export(*, out: str = "pack.json", mode: str = "category_sweep") -> dict:
    """Full corpus-only run. Returns a counts dict. Writes <out> (JSON) and the
    Markdown twin alongside it."""
    cfg = load_default()
    adv = load_advanced()
    project_name = cfg.get("project_name", "Lacuna Seed")
    sm = build_sessionmaker()

    async with sm() as session:
        proj = await _load_project(session, project_name)
        if proj is None:
            raise RuntimeError(f"project {project_name!r} not seeded yet — run `lacuna seed` first")
        works = (await session.execute(
            select(Work).where(Work.project_id == proj.id))).scalars().all()
        clusters = (await session.execute(
            select(AspectCluster).where(AspectCluster.project_id == proj.id))).scalars().all()
        rc_rows = (await session.execute(
            select(Review.work_id, func.count()).where(Review.project_id == proj.id)
            .group_by(Review.work_id))).all()
    review_counts = {wid: n for wid, n in rc_rows}

    clusters_by_work: dict[object, list[AspectCluster]] = {}
    for c in clusters:
        clusters_by_work.setdefault(c.work_id, []).append(c)

    # Build cohort candidates (F). demand/supply absent in the $0 corpus-only path.
    candidates, work_by_ref = [], {}
    for w in works:
        wc = clusters_by_work.get(w.id, [])
        cand = derive_components(
            ref_id=str(w.id), scope="work",
            demand_rows=[],            # no demand_signals seeded -> demand absent (withheld)
            title_count=None,          # no supply_signals seeded -> scarcity absent
            cluster_weights=[(c.reviewer_count, float(c.helpful_weight or 0.0)) for c in wc],
            sample_size=review_counts.get(w.id, 0),
            platforms=("amazon_corpus",),
        )
        candidates.append(cand)
        work_by_ref[str(w.id)] = w

    results = score_cohort(candidates, load_cfg())

    # Cross-platform agreement (corpus-only -> single platform -> 0.0, but compute honestly).
    embedder = Embedder()
    all_cluster_ins = [
        AspectClusterIn(label=c.label, platform=(c.platforms[0] if c.platforms else "amazon_corpus"),
                        reviewer_count=c.reviewer_count, helpful_weight=float(c.helpful_weight or 0.0),
                        member_count=c.member_count)
        for c in clusters
    ]
    merged = merge_clusters(all_cluster_ins, embedder=embedder.encode,
                            threshold=float(adv.get("cluster_merge_similarity", 0.75))) if all_cluster_ins else []
    agreement = agreement_pct(merged, top_n=int(cfg.get("export", {}).get("max_candidates", 15)))

    # Persist scores + assemble the pack.
    pack_candidates: list[PackCandidate] = []
    async with sm() as session:
        async with session.begin():
            for r in results:
                session.add(Score(
                    project_id=proj.id, scope=r.scope, ref_id=r.ref_id,
                    demand_score=r.demand_score, supply_scarcity=r.supply_scarcity,
                    unmet_need=r.unmet_need, gap_score=r.gap_score, confidence=r.confidence,
                    sample_size=r.sample_size, platforms_used=r.platforms_used,
                    oldest_signal=r.oldest_signal, newest_signal=r.newest_signal,
                    incomplete=r.incomplete, blind_spot=r.blind_spot,
                    recent_supply_surge=r.recent_supply_surge,
                ))
                w = work_by_ref[r.ref_id]
                wc = sorted(clusters_by_work.get(w.id, []),
                            key=lambda c: c.reviewer_count, reverse=True)
                pack_candidates.append(PackCandidate(
                    ref="work", title_or_subject=w.title,
                    gap_score=float(r.gap_score) if r.gap_score is not None else 0.0,
                    demand=float(r.demand_score) if r.demand_score is not None else 0.0,
                    supply_scarcity=float(r.supply_scarcity) if r.supply_scarcity is not None else 0.0,
                    unmet_need=float(r.unmet_need) if r.unmet_need is not None else 0.0,
                    confidence=float(r.confidence), sample_size=r.sample_size,
                    platforms=r.platforms_used,
                    oldest_signal=r.oldest_signal.isoformat() if r.oldest_signal else None,
                    newest_signal=r.newest_signal.isoformat() if r.newest_signal else None,
                    incomplete=r.incomplete, blind_spot=r.blind_spot,
                    recent_supply_surge=r.recent_supply_surge,
                    top_complaints=[Complaint(
                        aspect=c.representative or c.label, reviewer_count=c.reviewer_count,
                        helpful_weight=float(c.helpful_weight or 0.0),
                        platforms=list(c.platforms), cross_platform=bool(c.cross_platform),
                    ) for c in wc[:5]],
                    demand_evidence={},
                ))

    total_reviews = sum(review_counts.values())
    pack = build_pack(
        project=project_name, bisac=cfg.get("target_bisac", []), mode=mode,
        generated_at=dt.datetime.now(dt.timezone.utc).isoformat(),
        platforms_used=["amazon_corpus"], total_reviews=total_reviews,
        cross_platform_agreement_pct=round(agreement, 3), candidates=pack_candidates,
        max_candidates=int(cfg.get("export", {}).get("max_candidates", 15)),
    )

    out_path = Path(out)
    out_path.write_text(json.dumps(pack, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path = out_path.with_suffix(".md")
    md_path.write_text(to_markdown(pack, token_budget=int(cfg.get("export", {}).get("token_budget", 4000))),
                       encoding="utf-8")

    return {"works": len(works), "clusters": len(clusters), "scores": len(results),
            "total_reviews": total_reviews, "agreement": round(agreement, 3),
            "json": str(out_path), "markdown": str(md_path)}
