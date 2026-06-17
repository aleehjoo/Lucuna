# lacuna/aggregation/persist.py
"""Read per-platform aspect_clusters -> merge -> upsert unified clusters with
cross_platform + platforms[]. Integration layer (needs Supabase + D embedder).
Pure merge logic is in cross_platform.py and fully unit-tested."""
from __future__ import annotations


async def fuse_project_clusters(project_id: str) -> None:  # pragma: no cover
    raise NotImplementedError("requires Supabase + local embedder; see cross_platform.merge_clusters")
