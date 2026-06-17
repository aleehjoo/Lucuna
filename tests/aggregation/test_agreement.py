# tests/aggregation/test_agreement.py
from lacuna.aggregation.cross_platform import MergedCluster, agreement_pct

def test_agreement_is_share_of_top_complaints_cross_platform():
    clusters = [
        MergedCluster("a", ("amazon_corpus", "hardcover"), 10, 5.0, 12, cross_platform=True),
        MergedCluster("b", ("amazon_corpus",), 8, 4.0, 9, cross_platform=False),
        MergedCluster("c", ("amazon_corpus", "hardcover"), 6, 3.0, 7, cross_platform=True),
        MergedCluster("d", ("hardcover",), 1, 0.5, 1, cross_platform=False),
    ]
    # top 3 by reviewer_count: a(10), b(8), c(6) -> 2 of 3 cross-platform
    assert abs(agreement_pct(clusters, top_n=3) - (2 / 3)) < 1e-9

def test_agreement_zero_when_empty():
    assert agreement_pct([], top_n=5) == 0.0
