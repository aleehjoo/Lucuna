# tests/aggregation/test_merge.py
import numpy as np
from lacuna.aggregation.cross_platform import AspectClusterIn, merge_clusters

def _vec_embedder(label_to_vec):
    return lambda labels: np.array([label_to_vec[l] for l in labels])

def test_similar_labels_merge_across_platforms():
    clusters = [
        AspectClusterIn(label="outdated examples", platform="amazon_corpus", reviewer_count=10, helpful_weight=5.0, member_count=12),
        AspectClusterIn(label="examples are outdated", platform="hardcover", reviewer_count=4, helpful_weight=2.0, member_count=5),
        AspectClusterIn(label="too expensive", platform="amazon_corpus", reviewer_count=3, helpful_weight=1.0, member_count=3),
    ]
    emb = _vec_embedder({
        "outdated examples": [1.0, 0.0], "examples are outdated": [0.99, 0.01], "too expensive": [0.0, 1.0],
    })
    merged = merge_clusters(clusters, embedder=emb, threshold=0.75)
    # the two outdated clusters merge; the price one stays separate
    assert len(merged) == 2
    outdated = [m for m in merged if m.cross_platform][0]
    assert set(outdated.platforms) == {"amazon_corpus", "hardcover"}
    assert outdated.reviewer_count == 14 and outdated.member_count == 17

def test_single_platform_clusters_flagged_not_cross():
    clusters = [AspectClusterIn(label="repetitive", platform="amazon_corpus", reviewer_count=2, helpful_weight=1.0, member_count=2)]
    emb = _vec_embedder({"repetitive": [1.0, 0.0]})
    merged = merge_clusters(clusters, embedder=emb, threshold=0.75)
    assert merged[0].cross_platform is False and merged[0].platforms == ("amazon_corpus",)
