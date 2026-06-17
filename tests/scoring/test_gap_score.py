# tests/scoring/test_gap_score.py
import math
from lacuna.scoring.components import Candidate
from lacuna.scoring.gap_score import compose_gap, score_cohort, DEFAULT_CFG

def test_compose_gap_known_vector():
    # demand_norm=0.5, supply_norm=0.8, unmet_norm=0.6 -> gap≈0.4780
    gap = compose_gap(0.5, 0.8, 0.6, DEFAULT_CFG)
    assert abs(gap - (math.sqrt(0.48) * (1/(1+math.exp(-0.8))))) < 1e-9

def test_demand_absent_is_withheld_not_zero():
    cands = [Candidate("w1", "work", demand=None, supply_scarcity=-5.0, unmet_need=3.0, sample_size=30)]
    res = score_cohort(cands, DEFAULT_CFG)[0]
    assert res.gap_score is None and res.incomplete is True

def test_missing_supply_is_imputed_not_zeroed():
    cands = [
        Candidate("a", "work", demand=10, supply_scarcity=-2.0, unmet_need=5.0, sample_size=30),
        Candidate("b", "work", demand=20, supply_scarcity=None, unmet_need=4.0, sample_size=30),  # impute
        Candidate("c", "work", demand=30, supply_scarcity=-8.0, unmet_need=6.0, sample_size=30),
    ]
    res = {r.ref_id: r for r in score_cohort(cands, DEFAULT_CFG)}
    assert res["b"].gap_score is not None        # imputed, not zeroed
    assert res["b"].incomplete is True

def test_blind_spot_set_for_thin_sample():
    cands = [Candidate("t", "work", demand=10, supply_scarcity=-3.0, unmet_need=2.0, sample_size=5)]
    assert score_cohort(cands, DEFAULT_CFG)[0].blind_spot is True

def test_recent_supply_surge_downweights():
    base = Candidate("x", "work", demand=10, supply_scarcity=-3.0, unmet_need=4.0, sample_size=30)
    surge = Candidate("y", "work", demand=10, supply_scarcity=-3.0, unmet_need=4.0, sample_size=30, recent_share=0.5)
    out = {r.ref_id: r for r in score_cohort([base, surge], DEFAULT_CFG)}
    assert out["y"].recent_supply_surge is True
    assert out["y"].gap_score <= out["x"].gap_score
