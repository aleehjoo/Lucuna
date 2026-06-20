# lacuna/seed/orchestrator.py
"""Seed integration core (PRD §6). `build_seed_plan` is PURE: it consumes corpus
iterators + an injected embedder/labeler and returns in-memory rows ready to
persist — no DB, no network beyond the injected iterators, no external LLM. The
async DB write lives in `lacuna.db.repository`. This split keeps the algorithm
unit-testable offline (fakes) while the live run exercises persistence.

Boundary (PRD §7): embeddings, clustering and zero-shot labeling all run through
the injected local components; raw review text never leaves the machine.
"""
from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field

from lacuna.nlp.clustering import cluster_embeddings, members_by_cluster
from lacuna.seed.normalization import NORM_VERSION, normalized_key
from lacuna.seed.seed import edition_from_meta, to_edition_input
from lacuna.seed.selection import select_critical_reviews, select_works_with_longtail
from lacuna.seed.works_grouping import EditionInput, group_editions

# --- approved seed defaults (documented in METHODOLOGY.md §C-integration) ---
# The McAuley corpus is huge and only linearly scannable when streamed, so a first
# seed is bounded. Raise these (CLI flags) for fuller coverage.
DEFAULT_META_LIMIT = 200_000     # max meta rows scanned for subject matches
DEFAULT_REVIEW_LIMIT = 1_000_000  # max review rows scanned for matched works
PLATFORM = "amazon_corpus"


@dataclass
class PlanReview:
    external_id: str
    work_key: str
    edition_asin: str | None
    rating: float
    helpful_votes: int
    review_date: object | None  # datetime | None
    text: str
    embedding: list[float] | None = None
    sentiment: float | None = None
    cluster_local_id: int | None = None  # index into the work's PlanClusters


@dataclass
class PlanCluster:
    local_id: int                    # globally unique within the plan (niche-level pass)
    label: str
    member_count: int
    reviewer_count: int
    helpful_weight: float
    representative: str
    work_key: str | None = None      # None = niche-level (pooled across the niche, §6.6)
    bisac_code: str | None = None
    platforms: list[str] = field(default_factory=lambda: [PLATFORM])


@dataclass
class PlanEdition:
    asin: str
    work_key: str
    parent_asin: str | None
    isbn13: str | None
    isbn10: str | None
    format: str
    price_cents: int | None


@dataclass
class PlanWork:
    normalized_key: str
    norm_version: int
    title: str
    author: str | None
    edition_asins: list[str]
    rating_avg: float | None
    rating_count: int


@dataclass
class SeedPlan:
    works: list[PlanWork] = field(default_factory=list)
    editions: list[PlanEdition] = field(default_factory=list)
    reviews: list[PlanReview] = field(default_factory=list)
    clusters: list[PlanCluster] = field(default_factory=list)
    counts: dict = field(default_factory=dict)


def _subject_match(meta: dict, keywords: list[str]) -> bool:
    """Precision-first subject match (PRD §6 first-pass filter). Keywords are
    matched against the Amazon CATEGORY path only (`categories` + `main_category`),
    NOT the title or description. A blurb that merely mentions "algorithms" or
    "workout programming" is not a programming book; matching free text pulled in
    heavy pollution (novels, fitness, kids' workbooks) that then dominated the
    clusterable set. Amazon categories are BISAC-derived and reliable, so keywords
    act as category-leaf terms (e.g. "programming" -> "Programming Languages")."""
    if not keywords:
        return True
    hay = " ".join([
        " ".join(meta.get("categories") or []),
        str(meta.get("main_category") or ""),
    ]).lower()
    return any(k.lower() in hay for k in keywords)


def _rating_sentiment(rating: float) -> float:
    """Documented proxy (PRD §7 leaves seed sentiment to a rating signal): map the
    1–5 star rating to [-1, 1]. No text leaves the machine to compute this."""
    return max(-1.0, min(1.0, (rating - 3.0) / 2.0))


def build_seed_plan(
    meta_source: Iterable[dict] | Iterator[dict],
    review_source: Iterable[dict] | Iterator[object],
    *,
    embedder,
    labeler,
    subject_keywords: list[str],
    cap_per_work: int,
    longtail_share: float,
    min_sample_gate: int,
    min_critical_per_work: int,
    trigram_threshold: float,
    max_works: int,
    bisac_code: str | None = None,
    meta_limit: int = DEFAULT_META_LIMIT,
    review_limit: int = DEFAULT_REVIEW_LIMIT,
    cluster_min_size: int = 2,
    on_progress=None,
    on_progress_event=None,
) -> SeedPlan:
    """Stream meta → editions → works, stream matched reviews, select works with a
    long-tail floor, then embed/cluster/label each selected work's critical reviews.

    `review_source` yields CorpusReview-like objects (attrs: asin, parent_asin,
    rating, text, helpful_vote, user_id, review_date). `embedder.encode(list[str])
    -> ndarray`; `labeler.label_cluster(list[str]) -> AspectResult(label, score,
    representative)`.

    `on_progress_event(dict)` is an OPTIONAL structured sibling of `on_progress`
    (Task 8): fired at the same existing log points with `{"step", "progress_pct",
    "counts"}` so a UI/jobs-table consumer can show progress without parsing log
    strings. Purely additive — does not change any seed math or counts.
    """
    _p = on_progress or (lambda _m: None)
    _pe = on_progress_event or (lambda _e: None)

    # ---- Pass 1: subject-matched meta -> editions keyed by parent_asin ----
    edition_inputs: list[EditionInput] = []
    edition_records: dict[str, object] = {}  # parent_asin -> EditionRecord
    meta_scanned = 0
    for meta in meta_source:
        meta_scanned += 1
        if meta_scanned > meta_limit:
            break
        if meta_scanned % 25_000 == 0:
            _p(f"meta scanned {meta_scanned:,} / {meta_limit:,} · subject editions {len(edition_inputs):,}")
            _pe({"step": "meta", "progress_pct": round(40.0 * min(meta_scanned / meta_limit, 1.0), 1),
                "counts": {"meta_scanned": meta_scanned, "subject_editions": len(edition_inputs)}})
        if not _subject_match(meta, subject_keywords):
            continue
        pa = meta.get("parent_asin")
        if not pa or pa in edition_records:
            continue
        rec = edition_from_meta({**meta, "asin": pa})  # meta is per-parent; asin := parent
        edition_records[pa] = rec
        edition_inputs.append(to_edition_input(rec))

    groups = group_editions(edition_inputs, trigram_threshold=trigram_threshold)
    _p(f"pass1 done: {len(edition_inputs):,} subject editions → {len(groups):,} works "
       f"(scanned {meta_scanned:,} meta rows)")
    _pe({"step": "meta", "progress_pct": 40.0,
        "counts": {"meta_scanned": meta_scanned, "subject_editions": len(edition_inputs),
                   "works_total": len(groups)}})
    # parent_asin -> work normalized_key
    work_key_by_parent: dict[str, str] = {}
    for g in groups:
        wkey = normalized_key(g.title, g.author)
        for m in g.members:
            work_key_by_parent[m.asin] = wkey
    matched_parents = set(work_key_by_parent)
    _p(f"matching reviews against {len(matched_parents):,} subject parent_asins…")
    _pe({"step": "reviews", "progress_pct": 40.0,
        "counts": {"subject_parent_asins": len(matched_parents)}})

    # ---- Pass 2: stream reviews, keep those for matched parents ----
    reviews_by_work: dict[str, list[object]] = {}
    ratings_by_work: dict[str, list[float]] = {}
    review_scanned = 0
    matched_reviews = 0
    for rv in review_source:
        review_scanned += 1
        if review_scanned > review_limit:
            break
        if review_scanned % 200_000 == 0:
            _p(f"reviews scanned {review_scanned:,} / {review_limit:,} · "
               f"matched {matched_reviews:,} across {len(reviews_by_work):,} works")
            _pe({"step": "reviews",
                "progress_pct": round(40.0 + 40.0 * min(review_scanned / review_limit, 1.0), 1),
                "counts": {"review_scanned": review_scanned, "matched_reviews": matched_reviews,
                          "works_matched": len(reviews_by_work)}})
        pa = getattr(rv, "parent_asin", None) or getattr(rv, "asin", None)
        if pa not in matched_parents:
            continue
        matched_reviews += 1
        wkey = work_key_by_parent[pa]
        reviews_by_work.setdefault(wkey, []).append(rv)
        ratings_by_work.setdefault(wkey, []).append(float(getattr(rv, "rating", 0) or 0))
    _p(f"pass2 done: {matched_reviews:,} matched reviews across {len(reviews_by_work):,} works "
       f"(scanned {review_scanned:,} review rows)")
    _pe({"step": "reviews", "progress_pct": 80.0,
        "counts": {"review_scanned": review_scanned, "matched_reviews": matched_reviews,
                   "works_matched": len(reviews_by_work)}})

    # ---- Select works by CLUSTERABLE critical mass (PRD §6.1.4) ----
    # Clustering only ever consumes critical reviews (rating <= 3), so selection
    # must too: a work below `min_critical_per_work` can only produce HDBSCAN
    # noise, never a cluster. Excluding such works narrows the §6.5 long tail
    # (documented deviation, METHODOLOGY.md §15); the long-tail floor still
    # operates within the clusterable band.
    crit_count = {
        k: sum(1 for x in ratings_by_work.get(k, []) if x <= 3)
        for k in reviews_by_work
    }
    work_dicts = [
        {"key": k, "review_count": crit_count[k]}
        for k in reviews_by_work if crit_count[k] >= min_critical_per_work
    ]
    selected = select_works_with_longtail(
        work_dicts, n=min(max_works, len(work_dicts)),
        longtail_share=longtail_share, low_threshold=min_sample_gate,
    )
    selected_keys = [w["key"] for w in selected]
    _p(f"selected {len(selected_keys):,} works (>= {min_critical_per_work} critical reviews, "
       f"long-tail floor) from {len(work_dicts):,} eligible / {len(reviews_by_work):,} matched "
       f"works; embedding/clustering now…")
    _pe({"step": "nlp", "progress_pct": 80.0,
        "counts": {"works_total": len(work_dicts), "works_selected": len(selected_keys)}})

    plan = SeedPlan()
    # work -> the group (for title/author/editions)
    group_by_key: dict[str, object] = {
        normalized_key(g.title, g.author): g for g in groups
    }

    # ---- Per-work: build works/editions/reviews + embed; pool for niche clustering ----
    # Clustering is NICHE-LEVEL (PRD §6.6): per-work HDBSCAN on a dozen reviews in
    # 384-dim cosine space almost always returns all-noise, so critical reviews are
    # POOLED across the selected works and clustered ONCE. Clusters carry
    # work_id=None (niche-level) + the niche bisac_code; member reviews keep their
    # own work_id, so per-work provenance survives.
    pooled_reviews: list[PlanReview] = []     # PlanReview objects, pooled across works
    pooled_src: list[object] = []             # parallel source reviews (uid / helpful_vote)
    pooled_texts: list[str] = []
    pooled_embeds: list[list[float]] = []
    for wi, wkey in enumerate(selected_keys, 1):
        g = group_by_key.get(wkey)
        if g is None:
            continue
        _p(f"  work {wi}/{len(selected_keys)}: {(g.title or '')[:50]!r} "
           f"({len(reviews_by_work.get(wkey, [])):,} reviews)")
        _pe({"step": "nlp",
            "progress_pct": round(80.0 + 15.0 * (wi / len(selected_keys) if selected_keys else 1.0), 1),
            "counts": {"work_index": wi, "works_selected": len(selected_keys)}})
        ratings = ratings_by_work.get(wkey, [])
        rating_avg = round(sum(ratings) / len(ratings), 2) if ratings else None
        plan.works.append(PlanWork(
            normalized_key=wkey, norm_version=NORM_VERSION,
            title=g.title, author=g.author,
            edition_asins=[m.asin for m in g.members],
            rating_avg=rating_avg, rating_count=len(ratings),
        ))
        for m in g.members:
            rec = edition_records[m.asin]
            plan.editions.append(PlanEdition(
                asin=rec.asin, work_key=wkey, parent_asin=rec.parent_asin,
                isbn13=rec.isbn13, isbn10=rec.isbn10, format=rec.format,
                price_cents=rec.price_cents,
            ))

        # ---- Critical-review selection + local embedding (clustering pooled below) ----
        critical = select_critical_reviews(reviews_by_work[wkey], cap=cap_per_work)
        texts = [getattr(r, "text", "") or "" for r in critical]
        work_reviews: list[PlanReview] = []
        for r in critical:
            asin = getattr(r, "parent_asin", None) or getattr(r, "asin", None)
            uid = getattr(r, "user_id", None)
            ts = getattr(r, "timestamp", None)
            work_reviews.append(PlanReview(
                external_id=f"{asin}:{uid}:{ts}",
                work_key=wkey, edition_asin=asin,
                rating=float(getattr(r, "rating", 0) or 0),
                helpful_votes=int(getattr(r, "helpful_vote", 0) or 0),
                review_date=getattr(r, "review_date", None),
                text=getattr(r, "text", "") or "",
                sentiment=_rating_sentiment(float(getattr(r, "rating", 0) or 0)),
            ))
        if texts:
            vecs = embedder.encode(texts)
            for pr, src, t, v in zip(work_reviews, critical, texts, vecs):
                pr.embedding = [float(x) for x in v]
                pooled_reviews.append(pr)
                pooled_src.append(src)
                pooled_texts.append(t)
                pooled_embeds.append(pr.embedding)
        plan.reviews.extend(work_reviews)

    # ---- Niche-level clustering: pool across the niche, cluster once (PRD §6.6) ----
    if pooled_embeds:
        labels = cluster_embeddings(pooled_embeds, min_cluster_size=cluster_min_size)
        for local_id, member_idxs in members_by_cluster(labels).items():
            members_src = [pooled_src[i] for i in member_idxs]
            m_texts = [pooled_texts[i] for i in member_idxs]
            aspect = labeler.label_cluster(m_texts)
            reviewer_ct = len({getattr(m, "user_id", None) for m in members_src})
            helpful_w = float(sum(int(getattr(m, "helpful_vote", 0) or 0) for m in members_src))
            plan.clusters.append(PlanCluster(
                local_id=int(local_id), label=aspect.label,
                member_count=len(member_idxs), reviewer_count=reviewer_ct,
                helpful_weight=helpful_w, representative=aspect.representative,
                work_key=None, bisac_code=bisac_code,
            ))
            for i in member_idxs:
                pooled_reviews[i].cluster_local_id = int(local_id)
    _p(f"niche clustering: {len(plan.clusters):,} clusters from "
       f"{len(pooled_embeds):,} pooled critical reviews")
    _pe({"step": "clustering", "progress_pct": 100.0,
        "counts": {"clusters": len(plan.clusters), "pooled_reviews": len(pooled_embeds)}})

    plan.counts = {
        "meta_scanned": meta_scanned - 1 if meta_scanned else 0,
        "review_scanned": review_scanned - 1 if review_scanned else 0,
        "subject_editions": len(edition_inputs),
        "works_total": len(work_dicts),
        "works_selected": len(plan.works),
        "editions": len(plan.editions),
        "reviews": len(plan.reviews),
        "clusters": len(plan.clusters),
    }
    return plan
