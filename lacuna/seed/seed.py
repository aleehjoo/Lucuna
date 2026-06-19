# lacuna/seed/seed.py
"""Offline seed orchestrator (PRD §6). Pure helpers are unit-tested; run_seed()
is the integration entrypoint (DB upsert + local NLP) exercised after Supabase +
models are available. NO external LLM is called here (PRD §7)."""
from __future__ import annotations

import re
from dataclasses import dataclass

from lacuna.seed.works_grouping import EditionInput

_FORMAT_MAP = [
    ("kindle", "kindle"), ("audiobook", "audiobook"), ("audible", "audiobook"),
    ("paperback", "paperback"), ("hardcover", "hardcover"), ("hardback", "hardcover"),
]


@dataclass
class EditionRecord:
    asin: str
    parent_asin: str | None
    title: str
    author: str | None
    isbn13: str | None
    isbn10: str | None
    format: str
    price_cents: int | None


def infer_format(text: str | None) -> str:
    t = (text or "").lower()
    for needle, fmt in _FORMAT_MAP:
        if needle in t:
            return fmt
    return "other"


def _price_to_cents(price) -> int | None:
    if price is None:
        return None
    try:
        return round(float(re.sub(r"[^0-9.]", "", str(price))) * 100)
    except (ValueError, TypeError):
        return None


def edition_from_meta(row: dict) -> EditionRecord:
    author = row.get("author")
    author_name = author.get("name") if isinstance(author, dict) else author
    details = row.get("details") or {}
    fmt_src = details.get("format") or row.get("format") or ""
    return EditionRecord(
        asin=row.get("asin", ""),
        parent_asin=row.get("parent_asin"),
        title=row.get("title", ""),
        author=author_name,
        isbn13=details.get("isbn_13") or row.get("isbn13"),
        isbn10=details.get("isbn_10") or row.get("isbn10"),
        format=infer_format(fmt_src),
        price_cents=_price_to_cents(row.get("price")),
    )


def to_edition_input(rec: EditionRecord) -> EditionInput:
    return EditionInput(asin=rec.asin, parent_asin=rec.parent_asin,
                        title=rec.title, author=rec.author)


def run_seed(rebuild: bool = True, reconcile: bool = False, *,
             max_works: int | None = None, meta_limit: int | None = None,
             review_limit: int | None = None) -> dict:  # pragma: no cover
    """Integration entrypoint. Streams corpus -> editions -> works -> critical
    review selection -> local embed/cluster/label (Workstream D) -> upsert to
    Supabase -> analysis_runs(mode='seed'). Requires DATABASE_URL + pinned models.

    Wiring only (the algorithm lives in lacuna.seed.orchestrator.build_seed_plan and
    persistence in lacuna.db.repository); kept import-light so the CLI loads fast and
    the heavy ML deps import lazily inside this call."""
    if reconcile:
        raise NotImplementedError(
            "--reconcile not implemented; use --rebuild for a full recompute (PRD §6.4)")
    if not rebuild:
        raise NotImplementedError("only --rebuild (full recompute) is implemented (PRD §6.4)")

    import asyncio

    from lacuna.adapters import corpus
    from lacuna.config import load_advanced, load_default
    from lacuna.db.repository import persist_seed_plan, record_run
    from lacuna.db.session import build_sessionmaker
    from lacuna.nlp.aspects import AspectLabeler
    from lacuna.nlp.embeddings import Embedder
    from lacuna.seed.orchestrator import (
        DEFAULT_META_LIMIT, DEFAULT_REVIEW_LIMIT, build_seed_plan,
    )

    import sys
    import time

    cfg = load_default()
    adv = load_advanced()
    subject_keywords = (cfg.get("subject_filter") or {}).get("keywords") or []

    _t0 = time.monotonic()

    def _progress(msg: str) -> None:
        print(f"[seed +{time.monotonic() - _t0:6.0f}s] {msg}", flush=True)
        sys.stdout.flush()

    plan = build_seed_plan(
        corpus.iter_meta(),
        corpus.iter_reviews(),
        embedder=Embedder(),
        labeler=AspectLabeler(),
        subject_keywords=subject_keywords,
        cap_per_work=int(adv.get("curated_reviews_per_work", 15)),
        longtail_share=float(adv.get("longtail_share", 0.3)),
        min_sample_gate=int(adv.get("min_sample_gate", 20)),
        min_critical_per_work=int(adv.get("min_critical_per_work", 5)),
        trigram_threshold=float(adv.get("works_trigram_threshold", 0.6)),
        max_works=max_works if max_works is not None else 25,
        bisac_code=(cfg.get("target_bisac") or [None])[0],
        meta_limit=meta_limit if meta_limit is not None else DEFAULT_META_LIMIT,
        review_limit=review_limit if review_limit is not None else DEFAULT_REVIEW_LIMIT,
        on_progress=_progress,
    )
    _progress(f"plan built: {plan.counts}")

    sm = build_sessionmaker()

    async def _persist() -> dict:
        counts = await persist_seed_plan(
            sm, plan,
            project_name=cfg.get("project_name", "Lacuna Seed"),
            target_bisac=cfg.get("target_bisac", []),
            subject_filter=cfg.get("subject_filter", {}),
            config={"seed": {"max_works": max_works, "meta_limit": meta_limit,
                             "review_limit": review_limit}},
            rebuild=rebuild,
        )
        pid = counts.get("project_id")
        await record_run(sm, mode="seed", target=cfg.get("project_name"),
                         sources_used=["amazon_corpus"], status="ok",
                         counts=counts, project_id=pid)
        return counts

    return asyncio.run(_persist())
