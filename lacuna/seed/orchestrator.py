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
    work_key: str
    local_id: int
    label: str
    member_count: int
    reviewer_count: int
    helpful_weight: float
    representative: str
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
    if not keywords:
        return True
    hay = " ".join([
        str(meta.get("title") or ""),
        " ".join(meta.get("categories") or []),
        str(meta.get("main_category") or ""),
        " ".join(meta.get("description") or []) if isinstance(meta.get("description"), list)
        else str(meta.get("description") or ""),
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
    trigram_threshold: float,
    max_works: int,
    meta_limit: int = DEFAULT_META_LIMIT,
    review_limit: int = DEFAULT_REVIEW_LIMIT,
    cluster_min_size: int = 2,
) -> SeedPlan:
    """Stream meta → editions → works, stream matched reviews, select works with a
    long-tail floor, then embed/cluster/label each selected work's critical reviews.

    `review_source` yields CorpusReview-like objects (attrs: asin, parent_asin,
    rating, text, helpful_vote, user_id, review_date). `embedder.encode(list[str])
    -> ndarray`; `labeler.label_cluster(list[str]) -> AspectResult(label, score,
    representative)`.
    """
    # ---- Pass 1: subject-matched meta -> editions keyed by parent_asin ----
    edition_inputs: list[EditionInput] = []
    edition_records: dict[str, object] = {}  # parent_asin -> EditionRecord
    meta_scanned = 0
    for meta in meta_source:
        meta_scanned += 1
        if meta_scanned > meta_limit:
            break
        if not _subject_match(meta, subject_keywords):
            continue
        pa = meta.get("parent_asin")
        if not pa or pa in edition_records:
            continue
        rec = edition_from_meta({**meta, "asin": pa})  # meta is per-parent; asin := parent
        edition_records[pa] = rec
        edition_inputs.append(to_edition_input(rec))

    groups = group_editions(edition_inputs, trigram_threshold=trigram_threshold)
    # parent_asin -> work normalized_key
    work_key_by_parent: dict[str, str] = {}
    for g in groups:
        wkey = normalized_key(g.title, g.author)
        for m in g.members:
            work_key_by_parent[m.asin] = wkey
    matched_parents = set(work_key_by_parent)

    # ---- Pass 2: stream reviews, keep those for matched parents ----
    reviews_by_work: dict[str, list[object]] = {}
    ratings_by_work: dict[str, list[float]] = {}
    review_scanned = 0
    for rv in review_source:
        review_scanned += 1
        if review_scanned > review_limit:
            break
        pa = getattr(rv, "parent_asin", None) or getattr(rv, "asin", None)
        if pa not in matched_parents:
            continue
        wkey = work_key_by_parent[pa]
        reviews_by_work.setdefault(wkey, []).append(rv)
        ratings_by_work.setdefault(wkey, []).append(float(getattr(rv, "rating", 0) or 0))

    # ---- Select works with a long-tail floor ----
    work_dicts = [
        {"key": k, "review_count": len(v)} for k, v in reviews_by_work.items()
    ]
    selected = select_works_with_longtail(
        work_dicts, n=min(max_works, len(work_dicts)),
        longtail_share=longtail_share, low_threshold=min_sample_gate,
    )
    selected_keys = [w["key"] for w in selected]

    plan = SeedPlan()
    # work -> the group (for title/author/editions)
    group_by_key: dict[str, object] = {}
    for g in groups:
        group_by_key[normalized_key(g.title, g.author)] = g

    for wkey in selected_keys:
        g = group_by_key.get(wkey)
        if g is None:
            continue
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

        # ---- Critical-review selection + local NLP per work ----
        critical = select_critical_reviews(reviews_by_work[wkey], cap=cap_per_work)
        texts = [getattr(r, "text", "") or "" for r in critical]
        plan_reviews: list[PlanReview] = []
        for r in critical:
            asin = getattr(r, "parent_asin", None) or getattr(r, "asin", None)
            uid = getattr(r, "user_id", None)
            ts = getattr(r, "timestamp", None)
            pr = PlanReview(
                external_id=f"{asin}:{uid}:{ts}",
                work_key=wkey, edition_asin=asin,
                rating=float(getattr(r, "rating", 0) or 0),
                helpful_votes=int(getattr(r, "helpful_vote", 0) or 0),
                review_date=getattr(r, "review_date", None),
                text=getattr(r, "text", "") or "",
                sentiment=_rating_sentiment(float(getattr(r, "rating", 0) or 0)),
            )
            plan_reviews.append(pr)

        if texts:
            vecs = embedder.encode(texts)
            for pr, v in zip(plan_reviews, vecs):
                pr.embedding = [float(x) for x in v]
            labels = cluster_embeddings(vecs, min_cluster_size=cluster_min_size)
            for local_id, member_idxs in members_by_cluster(labels).items():
                members = [critical[i] for i in member_idxs]
                m_texts = [texts[i] for i in member_idxs]
                aspect = labeler.label_cluster(m_texts)
                reviewer_ct = len({getattr(m, "user_id", None) for m in members})
                helpful_w = float(sum(int(getattr(m, "helpful_vote", 0) or 0) for m in members))
                plan.clusters.append(PlanCluster(
                    work_key=wkey, local_id=int(local_id), label=aspect.label,
                    member_count=len(member_idxs), reviewer_count=reviewer_ct,
                    helpful_weight=helpful_w, representative=aspect.representative,
                ))
                for i in member_idxs:
                    plan_reviews[i].cluster_local_id = int(local_id)
        plan.reviews.extend(plan_reviews)

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
