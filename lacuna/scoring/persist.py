# lacuna/scoring/persist.py
"""Read distilled tables -> Candidates; write ScoreResults -> scores. Integration
layer (needs Supabase). Pure scoring is in gap_score.py and fully unit-tested."""
from __future__ import annotations

from lacuna.scoring.components import Candidate
from lacuna.scoring.gap_score import ScoreResult


async def load_candidates(project_id: str, scope: str) -> list[Candidate]:  # pragma: no cover
    raise NotImplementedError("requires Supabase; see gap_score.score_cohort for the pure logic")


async def write_scores(project_id: str, results: list[ScoreResult]) -> None:  # pragma: no cover
    raise NotImplementedError("requires Supabase; upserts into scores (unique project_id,scope,ref_id)")
