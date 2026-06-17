# tests/scoring/test_validity.py
from lacuna.scoring.validity import compute_confidence, clamp01

def test_clamp():
    assert clamp01(-0.2) == 0.0 and clamp01(1.5) == 1.0 and clamp01(0.4) == 0.4

def test_confidence_full_data_two_platforms():
    c = compute_confidence(sample_size=40, min_sample_gate=20, imputed_layers=0,
                           single_platform=False, crosswalk_conf=1.0)
    assert abs(c - 1.0) < 1e-9

def test_confidence_penalised_for_small_sample_imputation_singleplatform():
    c = compute_confidence(sample_size=10, min_sample_gate=20, imputed_layers=1,
                           single_platform=True, crosswalk_conf=0.9)
    assert abs(c - (0.5 * 0.7 * 0.85 * 0.9)) < 1e-9
