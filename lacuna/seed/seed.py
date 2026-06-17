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


def run_seed(rebuild: bool = False, reconcile: bool = False) -> None:  # pragma: no cover
    """Integration entrypoint (deferred). Streams corpus -> editions -> works ->
    critical review selection -> local embed/cluster/label (Workstream D) -> upsert
    to Supabase -> analysis_runs(mode='seed'). Requires DATABASE_URL + pinned models."""
    if reconcile:
        raise NotImplementedError(
            "--reconcile not implemented; use --rebuild for a full recompute (PRD §6.4)")
    raise NotImplementedError(
        "run_seed requires Supabase credentials and pinned models; run after `alembic upgrade head`")
