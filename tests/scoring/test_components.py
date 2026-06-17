# tests/scoring/test_components.py
from lacuna.scoring.components import Candidate, derive_components

def test_present_zero_is_genuine_and_absent_is_none():
    c = derive_components(
        ref_id="w1", scope="work",
        demand_rows=[{"value": 5.0}],            # demand present
        title_count=0,                            # genuine zero supply -> scarcity present, max
        cluster_weights=[],                       # no clusters -> unmet absent
    )
    assert isinstance(c, Candidate)
    assert c.demand is not None
    assert c.supply_scarcity is not None          # title_count present (even 0)
    assert c.unmet_need is None                    # absent (no clusters), NOT zero

def test_unmet_need_is_sum_of_reviewer_times_helpful():
    c = derive_components(ref_id="w", scope="work", demand_rows=[{"value": 1}],
                          title_count=10,
                          cluster_weights=[(3, 2.0), (1, 1.0)])  # (reviewer_count, helpful_weight)
    assert c.unmet_need == 3 * 2.0 + 1 * 1.0

def test_demand_absent_when_no_rows():
    c = derive_components(ref_id="w", scope="work", demand_rows=[],
                          title_count=10, cluster_weights=[(1, 1.0)])
    assert c.demand is None
