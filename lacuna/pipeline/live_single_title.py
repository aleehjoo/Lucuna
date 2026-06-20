# lacuna/pipeline/live_single_title.py
"""Live single-title analysis (Frontend PRD §3.2) — NEW glue composing EXISTING
components. Distinct from the batch seed and from the corpus-only single_title path.

Flow: resolve+pull title from Hardcover (live, seconds) -> embed + HDBSCAN cluster
the fresh reviews with the WARM models -> label each cluster (paraphrase only) ->
if seeded corpus clusters exist for the title, merge via cross_platform (agreement
raises confidence) -> score + build a Context Pack. The corpus is NEVER scanned here
(§1.2 HARD RULE): only Hardcover is called live.

Every heavy component is injected so this is unit-testable offline and so the API
passes its WARM singleton in (models never reload per request, §13.4). No raw review
text leaves the machine — clustering/labeling are local; the pack carries paraphrases
only (CLAUDE.md §3)."""
from __future__ import annotations

import datetime as dt

from lacuna.aggregation.cross_platform import (
    AspectClusterIn, MergedCluster, agreement_pct, merge_clusters,
)
from lacuna.export.context_pack import Candidate, Complaint, build_pack
from lacuna.nlp.clustering import cluster_embeddings, members_by_cluster


async def analyze_live(*, title: str, hardcover, embedder, labeler,
                       seeded_clusters: list[AspectClusterIn] | None = None,
                       cluster_min_size: int = 2, review_limit: int = 50,
                       progress_cb=None) -> dict:
    def _tick(step, pct):
        if progress_cb:
            progress_cb({"step": step, "progress_pct": pct})

    _tick("resolving", 10.0)
    book = await hardcover.fetch_book_by_title(title, review_limit=review_limit)
    if book is None:
        return {"title": title, "fresh_only": not seeded_clusters, "review_count": 0,
                "clusters": [], "agreement_pct": 0.0, "not_found": True,
                "pack": build_pack(project=title, bisac=[], mode="single_title",
                                   generated_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                                   platforms_used=[], total_reviews=0,
                                   cross_platform_agreement_pct=0.0, candidates=[], max_candidates=15)}

    # Only critical reviews carry dissatisfaction signal (rating <= 3), mirroring the seed.
    crit = [r for r in book.reviews if (r.rating is None or float(r.rating) <= 3) and (r.body or "").strip()]
    texts = [r.body for r in crit]
    review_count = len(book.reviews)

    _tick("embedding", 40.0)
    fresh_clusters: list[AspectClusterIn] = []
    fresh_dicts: list[dict] = []
    if len(texts) >= cluster_min_size:
        embeds = embedder.encode(texts)
        labels = cluster_embeddings(embeds, min_cluster_size=cluster_min_size)
        _tick("labeling", 70.0)
        for _cid, idxs in members_by_cluster(labels).items():
            members = [texts[i] for i in idxs]
            res = labeler.label_cluster(members)
            reviewer_count = len(idxs)
            helpful = 0.0  # Hardcover has no helpful-vote signal
            fresh_clusters.append(AspectClusterIn(
                label=res.label, platform="hardcover", reviewer_count=reviewer_count,
                helpful_weight=helpful, member_count=reviewer_count))
            fresh_dicts.append({"label": res.label, "representative": res.representative,
                                "reviewer_count": reviewer_count, "platforms": ["hardcover"],
                                "cross_platform": False})

    # Merge with seeded corpus clusters if the title was seeded; else fresh-only.
    fresh_only = not seeded_clusters
    all_in = list(fresh_clusters) + list(seeded_clusters or [])
    _tick("merging", 85.0)
    merged: list[MergedCluster] = merge_clusters(
        all_in, embedder=embedder.encode, threshold=0.75) if all_in else []
    agreement = agreement_pct(merged, top_n=15)

    cluster_view = [{"label": m.label, "representative": m.label,
                     "reviewer_count": m.reviewer_count, "platforms": list(m.platforms),
                     "cross_platform": m.cross_platform} for m in merged] or fresh_dicts

    # Build a single-candidate pack for this title from the merged complaints.
    _tick("exporting", 95.0)
    complaints = [Complaint(aspect=m.label, reviewer_count=m.reviewer_count,
                            helpful_weight=m.helpful_weight, platforms=list(m.platforms),
                            cross_platform=m.cross_platform)
                  for m in sorted(merged, key=lambda c: c.reviewer_count, reverse=True)[:5]]
    cand = Candidate(
        ref="work", title_or_subject=book.title, gap_score=0.0, demand=0.0,
        supply_scarcity=0.0, unmet_need=0.0,
        confidence=min(1.0, 0.2 + 0.1 * len(merged) + (0.3 if not fresh_only else 0.0)),
        sample_size=len(texts),
        platforms=sorted({p for m in merged for p in m.platforms}) or ["hardcover"],
        oldest_signal=None, newest_signal=None,
        incomplete=fresh_only, blind_spot=len(texts) < 5, recent_supply_surge=False,
        top_complaints=complaints, demand_evidence={})
    pack = build_pack(
        project=book.title, bisac=[], mode="single_title",
        generated_at=dt.datetime.now(dt.timezone.utc).isoformat(),
        platforms_used=cand.platforms, total_reviews=len(texts),
        cross_platform_agreement_pct=round(agreement, 3), candidates=[cand], max_candidates=15)

    _tick("done", 100.0)
    return {"title": book.title, "fresh_only": fresh_only, "review_count": review_count,
            "clusters": cluster_view, "agreement_pct": round(agreement, 3), "pack": pack}
