# lacuna/pipeline/freshness.py
"""Pure helper for the timely<->evergreen freshness indicator (PRD §14).
Dims toward 'timely' to honestly signal the fresh layer is thinner."""
from __future__ import annotations

MIN_OPACITY = 0.3
MAX_OPACITY = 1.0


def freshness_opacity(slider: float) -> float:
    """slider in [0,1]: 0=evergreen (full opacity), 1=timely (dimmed)."""
    s = max(0.0, min(1.0, slider))
    return MAX_OPACITY - s * (MAX_OPACITY - MIN_OPACITY)
