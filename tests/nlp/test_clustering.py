# tests/nlp/test_clustering.py
import numpy as np
from lacuna.nlp.clustering import cluster_embeddings, members_by_cluster

def test_two_separated_groups_form_clusters():
    # two tight groups in cosine space
    g1 = np.tile(np.array([1.0, 0.0, 0.0]), (5, 1)) + np.random.RandomState(0).normal(0, 1e-3, (5, 3))
    g2 = np.tile(np.array([0.0, 1.0, 0.0]), (5, 1)) + np.random.RandomState(1).normal(0, 1e-3, (5, 3))
    labels = cluster_embeddings(np.vstack([g1, g2]), min_cluster_size=2)
    # at least 2 distinct non-noise clusters
    assert len({l for l in labels if l != -1}) >= 2

def test_small_n_returns_all_noise():
    labels = cluster_embeddings(np.array([[1.0, 0.0, 0.0]]), min_cluster_size=2)
    assert list(labels) == [-1]

def test_members_by_cluster_excludes_noise():
    labels = np.array([-1, 0, 0, 1, -1])
    m = members_by_cluster(labels)
    assert m == {0: [1, 2], 1: [3]}
