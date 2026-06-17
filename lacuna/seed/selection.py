# lacuna/seed/selection.py
"""Pure selection helpers for the seed pass (PRD §6.1.4, §6.5)."""
from __future__ import annotations

import math
from typing import Any


def select_critical_reviews(reviews: list[Any], *, cap: int) -> list[Any]:
    """Keep critical reviews (rating <= 3), ranked by helpful_vote desc, capped."""
    critical = [r for r in reviews if (r.rating or 0) <= 3]
    critical.sort(key=lambda r: (r.helpful_vote or 0), reverse=True)
    return critical[:cap]


def select_works_with_longtail(
    works: list[dict], *, n: int, longtail_share: float, low_threshold: int,
) -> list[dict]:
    """Select n works ensuring at least ceil(n*longtail_share) low-review works,
    so survivorship bias does not re-enter at ingestion (PRD §6.5)."""
    low = [w for w in works if w["review_count"] < low_threshold]
    high = [w for w in works if w["review_count"] >= low_threshold]
    # high-review first by count desc; low-review by count desc too
    high.sort(key=lambda w: w["review_count"], reverse=True)
    low.sort(key=lambda w: w["review_count"], reverse=True)

    want_low = min(len(low), math.ceil(n * longtail_share))
    chosen = low[:want_low]
    chosen += high[: n - len(chosen)]
    # if still short (few high), backfill from remaining low
    if len(chosen) < n:
        chosen += low[want_low: want_low + (n - len(chosen))]
    return chosen[:n]
