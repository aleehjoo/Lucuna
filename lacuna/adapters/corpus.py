# lacuna/adapters/corpus.py
"""McAuley Amazon Reviews 2023 streaming adapter (PRD §4/§6).
Loads raw parquet configs with the pinned revision; streaming only; raw text
never written to the repo."""
from __future__ import annotations

from collections.abc import Iterable, Iterator

from lacuna.config import load_advanced
from lacuna.schemas.sources import CorpusReview

CORPUS_NAME = "McAuley-Lab/Amazon-Reviews-2023"
REVIEW_CONFIG = "raw_review_Books"
META_CONFIG = "raw_meta_Books"


def _pinned_revision() -> str:
    rev = load_advanced().get("dataset", {}).get("amazon_reviews", {}).get("revision")
    if not rev or rev == "<resolved-at-build>":
        raise RuntimeError("dataset revision not pinned — run scripts/pin_revisions.py (PRD §15)")
    return rev


def _hf_stream(config: str) -> Iterator[dict]:
    from datasets import load_dataset
    ds = load_dataset(
        CORPUS_NAME, config, split="full",
        streaming=True, revision=_pinned_revision(),
    )
    yield from ds


def iter_reviews(_source: Iterable[dict] | None = None) -> Iterator[CorpusReview]:
    """Yield validated reviews. `_source` injectable for tests; defaults to HF stream."""
    source = _source if _source is not None else _hf_stream(REVIEW_CONFIG)
    for row in source:
        yield CorpusReview.model_validate(row)


def iter_meta(_source: Iterable[dict] | None = None) -> Iterator[dict]:
    """Yield raw metadata rows (parsed into editions in Workstream C)."""
    source = _source if _source is not None else _hf_stream(META_CONFIG)
    yield from source
