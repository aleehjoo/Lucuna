# lacuna/pipeline/single_title.py
"""Single-Title Watchlist pipeline (PRD §11): resolve work -> fresh pull (Hardcover/
Google Books) -> merge with corpus clusters (G) -> score (F) -> export (H).

The fresh pull needs a live HARDCOVER_API_TOKEN in .env, so `analyze` is wired for
the post-credentials phase. `export_only` regenerates the Context Pack from the
already-seeded corpus data and runs at $0 (no keys)."""
from __future__ import annotations


async def analyze(*, isbn: str | None, title: str | None, out: str) -> None:  # pragma: no cover
    raise NotImplementedError(
        "single_title.analyze: needs a live HARDCOVER_API_TOKEN in .env for the fresh pull. "
        "Paste the rotated token, then re-run. Corpus-only export is available via `lacuna export`.")


async def export_only(*, out: str) -> dict:
    """(Re)generate the Context Pack from the latest seeded corpus data ($0)."""
    from lacuna.pipeline.distill import distill_score_export
    return await distill_score_export(out=out, mode="single_title")
