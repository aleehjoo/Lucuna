# lacuna/scoring/normalize.py
"""Pure scoring math (PRD §10)."""
from __future__ import annotations

import math

from scipy.stats import rankdata


def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def rank_normalize(values: list[float]) -> list[float]:
    """Percentile-rank to [0,1]: (rank-1)/(n-1). n==1 → 0.5 (neutral). Outlier-robust."""
    n = len(values)
    if n == 0:
        return []
    if n == 1:
        return [0.5]
    ranks = rankdata(values, method="average")  # 1..n, ties averaged
    return [(r - 1) / (n - 1) for r in ranks]


def weighted_geomean(values: list[float], weights: list[float]) -> float:
    """(∏ v_i^w_i)^(1/Σw). pow-form so a genuine 0 → 0 without log(0)."""
    total = sum(weights)
    prod = 1.0
    for v, w in zip(values, weights):
        prod *= max(0.0, min(1.0, v)) ** w
    return prod ** (1.0 / total)
