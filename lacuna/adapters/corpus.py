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

# The dataset's loading script is no longer supported by `datasets` (>=2.x dropped
# script execution: "Dataset scripts are no longer supported"). Stream the underlying
# raw JSONL files directly from the Hub at the pinned revision instead — same data,
# no script, and revision pinning (PRD §15) is preserved.
_CONFIG_FILE = {
    REVIEW_CONFIG: "raw/review_categories/Books.jsonl",
    META_CONFIG: "raw/meta_categories/meta_Books.jsonl",
}


def _pinned_revision() -> str:
    rev = load_advanced().get("dataset", {}).get("amazon_reviews", {}).get("revision")
    if not rev or rev == "<resolved-at-build>":
        raise RuntimeError("dataset revision not pinned — run scripts/pin_revisions.py (PRD §15)")
    return rev


def _hf_stream(config: str) -> Iterator[dict]:
    import json

    from huggingface_hub import HfFileSystem

    path = _CONFIG_FILE.get(config)
    if path is None:
        raise ValueError(f"unknown corpus config {config!r}")
    fs = HfFileSystem()
    full = f"datasets/{CORPUS_NAME}/{path}"
    # Binary stream + per-line json.loads keeps memory flat over a multi-GB file.
    with fs.open(full, "rb", revision=_pinned_revision()) as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def iter_reviews(_source: Iterable[dict] | None = None) -> Iterator[CorpusReview]:
    """Yield validated reviews. `_source` injectable for tests; defaults to HF stream."""
    source = _source if _source is not None else _hf_stream(REVIEW_CONFIG)
    for row in source:
        yield CorpusReview.model_validate(row)


def iter_meta(_source: Iterable[dict] | None = None) -> Iterator[dict]:
    """Yield raw metadata rows (parsed into editions in Workstream C)."""
    source = _source if _source is not None else _hf_stream(META_CONFIG)
    yield from source
