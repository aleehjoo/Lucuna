# lacuna/scoring/components.py
"""Derive the three raw scoring components from distilled data (PRD §9/§10).
None means ABSENT (never treated as zero); a real 0.0 propagates."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass
class Candidate:
    ref_id: str
    scope: str  # 'work' | 'bisac'
    demand: float | None
    supply_scarcity: float | None
    unmet_need: float | None
    sample_size: int = 0
    platforms: tuple[str, ...] = ()
    oldest_signal: date | None = None
    newest_signal: date | None = None
    crosswalk_conf: float = 1.0
    recent_share: float = 0.0  # recent_title_count / title_count


def derive_components(
    *, ref_id: str, scope: str,
    demand_rows: list[dict],
    title_count: int | None,
    cluster_weights: list[tuple[int, float]],
    sample_size: int = 0,
    platforms: tuple[str, ...] = (),
    oldest_signal: date | None = None,
    newest_signal: date | None = None,
    crosswalk_conf: float = 1.0,
    recent_share: float = 0.0,
) -> Candidate:
    # demand: present iff >=1 demand_signal row; sum of available metric values
    demand = sum(float(r["value"]) for r in demand_rows) if demand_rows else None
    # supply_scarcity: inverse of supply. present iff title_count is not None (0 is genuine).
    supply_scarcity = (float(-title_count)) if title_count is not None else None
    # unmet_need: sum(reviewer_count * helpful_weight); absent iff no clusters
    unmet_need = sum(rc * hw for rc, hw in cluster_weights) if cluster_weights else None
    return Candidate(
        ref_id=ref_id, scope=scope, demand=demand,
        supply_scarcity=supply_scarcity, unmet_need=unmet_need,
        sample_size=sample_size, platforms=tuple(platforms),
        oldest_signal=oldest_signal, newest_signal=newest_signal,
        crosswalk_conf=crosswalk_conf, recent_share=recent_share,
    )
