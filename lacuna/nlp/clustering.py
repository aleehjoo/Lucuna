# lacuna/nlp/clustering.py
"""HDBSCAN clustering over embeddings in cosine space (PRD §7). Pure; no model."""
from __future__ import annotations

import hdbscan
import numpy as np
from sklearn.metrics import pairwise_distances


def cluster_embeddings(vectors, min_cluster_size: int = 2) -> np.ndarray:
    """Return a cluster label per row; noise = -1. Uses a precomputed cosine
    distance matrix. Guards small n (< min_cluster_size) by returning all-noise."""
    X = np.asarray(vectors, dtype="float64")
    if X.ndim != 2 or len(X) < min_cluster_size:
        return np.full(len(X), -1, dtype=int)
    distances = pairwise_distances(X, metric="cosine").astype("float64")
    clusterer = hdbscan.HDBSCAN(min_cluster_size=min_cluster_size, metric="precomputed")
    return clusterer.fit_predict(distances)


def members_by_cluster(labels) -> dict[int, list[int]]:
    """Map cluster_id -> member row indices, excluding noise (-1)."""
    out: dict[int, list[int]] = {}
    for idx, lab in enumerate(labels):
        lab = int(lab)
        if lab == -1:
            continue
        out.setdefault(lab, []).append(idx)
    return out
