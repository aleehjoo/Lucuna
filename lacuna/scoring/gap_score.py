# lacuna/scoring/gap_score.py
"""Cohort-level resilient gap scoring (PRD §10). Pure; DB I/O lives in the pipeline."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from statistics import median

from lacuna.scoring.components import Candidate
from lacuna.scoring.normalize import rank_normalize, sigmoid, weighted_geomean
from lacuna.scoring.validity import clamp01, compute_confidence

DEFAULT_CFG = {
    "demand_gate_floor_epsilon": 0.05,
    "demand_gate_steepness_k": 8,
    "demand_gate_midpoint_d0": 0.4,
    "geomean_weight_supply": 1.0,
    "geomean_weight_unmet": 1.0,
    "min_sample_gate": 20,
    "recent_supply_surge_threshold": 0.30,
    "recent_supply_surge_downweight": 0.7,
}


@dataclass
class ScoreResult:
    ref_id: str
    scope: str
    demand_score: float | None
    supply_scarcity: float | None
    unmet_need: float | None
    gap_score: float | None
    confidence: float
    sample_size: int
    platforms_used: list[str]
    oldest_signal: date | None
    newest_signal: date | None
    incomplete: bool
    blind_spot: bool
    recent_supply_surge: bool


def compose_gap(demand_norm: float, supply_norm: float, unmet_norm: float, cfg: dict) -> float:
    gate = max(cfg["demand_gate_floor_epsilon"],
               sigmoid(cfg["demand_gate_steepness_k"] * (demand_norm - cfg["demand_gate_midpoint_d0"])))
    core = weighted_geomean([supply_norm, unmet_norm],
                            [cfg["geomean_weight_supply"], cfg["geomean_weight_unmet"]])
    return core * gate


def _normalize_with_imputation(raw: list[float | None]) -> tuple[list[float], list[bool]]:
    """Rank-normalize present values to [0,1]; impute missing as the median of the
    present normalized values. Returns (norms, imputed_flags)."""
    present_idx = [i for i, v in enumerate(raw) if v is not None]
    present_norms = rank_normalize([raw[i] for i in present_idx])
    norm_map = dict(zip(present_idx, present_norms))
    fill = median(present_norms) if present_norms else 0.5
    norms, imputed = [], []
    for i in range(len(raw)):
        if i in norm_map:
            norms.append(norm_map[i]); imputed.append(False)
        else:
            norms.append(fill); imputed.append(True)
    return norms, imputed


def score_cohort(candidates: list[Candidate], cfg: dict = DEFAULT_CFG) -> list[ScoreResult]:
    # Demand: candidates missing demand are WITHHELD; rank-normalize the rest together.
    demand_present = [c.demand is not None for c in candidates]
    demand_norm_map: dict[int, float] = {}
    present_idx = [i for i, p in enumerate(demand_present) if p]
    for i, dn in zip(present_idx, rank_normalize([candidates[i].demand for i in present_idx])):
        demand_norm_map[i] = dn

    supply_norms, supply_imp = _normalize_with_imputation([c.supply_scarcity for c in candidates])
    unmet_norms, unmet_imp = _normalize_with_imputation([c.unmet_need for c in candidates])

    results: list[ScoreResult] = []
    for i, c in enumerate(candidates):
        surge = c.recent_share > cfg["recent_supply_surge_threshold"]
        blind = c.sample_size < cfg["min_sample_gate"]
        imputed_layers = int(supply_imp[i]) + int(unmet_imp[i])

        if not demand_present[i]:
            results.append(ScoreResult(
                c.ref_id, c.scope, None, supply_norms[i], unmet_norms[i], None,
                confidence=compute_confidence(sample_size=c.sample_size,
                    min_sample_gate=cfg["min_sample_gate"], imputed_layers=imputed_layers + 1,
                    single_platform=len(c.platforms) <= 1, crosswalk_conf=c.crosswalk_conf),
                sample_size=c.sample_size, platforms_used=list(c.platforms),
                oldest_signal=c.oldest_signal, newest_signal=c.newest_signal,
                incomplete=True, blind_spot=blind, recent_supply_surge=surge))
            continue

        gap = compose_gap(demand_norm_map[i], supply_norms[i], unmet_norms[i], cfg)
        if surge:
            gap *= cfg["recent_supply_surge_downweight"]
        results.append(ScoreResult(
            c.ref_id, c.scope, demand_norm_map[i], supply_norms[i], unmet_norms[i], clamp01(gap),
            confidence=compute_confidence(sample_size=c.sample_size,
                min_sample_gate=cfg["min_sample_gate"], imputed_layers=imputed_layers,
                single_platform=len(c.platforms) <= 1, crosswalk_conf=c.crosswalk_conf),
            sample_size=c.sample_size, platforms_used=list(c.platforms),
            oldest_signal=c.oldest_signal, newest_signal=c.newest_signal,
            incomplete=imputed_layers > 0, blind_spot=blind, recent_supply_surge=surge))
    return results


def load_cfg() -> dict:  # pragma: no cover
    """Merge advanced.yaml knobs over DEFAULT_CFG (used by the pipeline)."""
    from lacuna.config import load_advanced
    adv = load_advanced()
    return {**DEFAULT_CFG, **{k: adv[k] for k in DEFAULT_CFG if k in adv}}
