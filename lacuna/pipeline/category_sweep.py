# lacuna/pipeline/category_sweep.py
"""Category Sweep pipeline (PRD §11): score the seeded works as a cohort and emit a
ranked Context Pack. Corpus-only and $0 (no external keys). Full BISAC-bucket fusion
(fresh demand/supply signals) layers on once those signals are seeded."""
from __future__ import annotations


async def sweep(*, out: str) -> dict:
    from lacuna.pipeline.distill import distill_score_export
    return await distill_score_export(out=out, mode="category_sweep")
