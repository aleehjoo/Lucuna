# tests/scoring/test_normalize.py
import math
from lacuna.scoring.normalize import rank_normalize, sigmoid, weighted_geomean

def test_rank_normalize_spreads_to_unit_interval():
    assert rank_normalize([10, 20, 30]) == [0.0, 0.5, 1.0]

def test_rank_normalize_is_outlier_robust():
    out = rank_normalize([1, 2, 3, 1000])
    assert out == [0.0, 1/3, 2/3, 1.0]

def test_rank_normalize_single_is_neutral():
    assert rank_normalize([42]) == [0.5]
    assert rank_normalize([]) == []

def test_sigmoid_midpoint():
    assert abs(sigmoid(0) - 0.5) < 1e-9

def test_weighted_geomean_equal_weights():
    assert abs(weighted_geomean([0.8, 0.6], [1.0, 1.0]) - math.sqrt(0.48)) < 1e-9

def test_weighted_geomean_genuine_zero_propagates():
    assert weighted_geomean([0.0, 0.9], [1.0, 1.0]) == 0.0
