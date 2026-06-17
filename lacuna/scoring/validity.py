# lacuna/scoring/validity.py
"""Confidence composite + clamp (PRD §10; approved formula in METHODOLOGY.md)."""
from __future__ import annotations


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def compute_confidence(*, sample_size: int, min_sample_gate: int, imputed_layers: int,
                       single_platform: bool, crosswalk_conf: float) -> float:
    sample_factor = min(1.0, sample_size / min_sample_gate) if min_sample_gate else 1.0
    imputation_factor = 0.7 ** imputed_layers
    platform_factor = 0.85 if single_platform else 1.0
    return clamp01(sample_factor * imputation_factor * platform_factor * crosswalk_conf)
