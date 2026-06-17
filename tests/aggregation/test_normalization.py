# tests/aggregation/test_normalization.py
from lacuna.aggregation.cross_platform import normalize_ratings_per_platform

def test_zscore_within_platform_independently():
    data = {"amazon_corpus": [1.0, 3.0, 5.0], "hardcover": [4.0, 4.0, 4.0]}
    out = normalize_ratings_per_platform(data)
    # amazon spread -> mean 3 -> middle is 0.0
    assert abs(out["amazon_corpus"][1] - 0.0) < 1e-9
    assert out["amazon_corpus"][0] < 0 < out["amazon_corpus"][2]
    # hardcover zero variance -> all 0.0 (min-max fallback), never NaN
    assert out["hardcover"] == [0.0, 0.0, 0.0]
