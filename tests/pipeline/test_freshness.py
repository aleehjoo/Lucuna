# tests/pipeline/test_freshness.py
from lacuna.pipeline.freshness import freshness_opacity


def test_evergreen_is_full_opacity():
    # slider 0 = evergreen depth -> indicator fully lit (fresh layer not emphasized)
    assert freshness_opacity(0.0) == 1.0


def test_timely_dims_indicator():
    # slider 1 = timely -> indicator dimmed (honest signal the fresh layer is thinner)
    assert freshness_opacity(1.0) == 0.3
    assert 0.3 < freshness_opacity(0.5) < 1.0


def test_clamped():
    assert freshness_opacity(-1) == 1.0 and freshness_opacity(2) == 0.3
