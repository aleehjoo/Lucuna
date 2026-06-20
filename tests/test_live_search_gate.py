# tests/test_live_search_gate.py
"""W4 GATE — mirrors the engine's G0 gate. Proves the live single-title path
(real Hardcover API + real local NLP models) works end-to-end on a real,
popular title. Slow; skipped in CI when HARDCOVER_API_TOKEN is absent, but
MUST be run manually and pass before Plan B (frontend, W5+) begins."""
import os

import pytest

from lacuna.adapters.hardcover import HardcoverClient
from lacuna.config import get_settings
from lacuna.nlp.aspects import AspectLabeler
from lacuna.nlp.embeddings import Embedder
from lacuna.pipeline.live_single_title import analyze_live

pytestmark = pytest.mark.skipif(
    not os.getenv("HARDCOVER_API_TOKEN"),
    reason="HARDCOVER_API_TOKEN not set — W4 live gate skipped",
)


async def test_live_search_produces_real_result_for_known_title():
    """W4 GATE (Frontend PRD §16): a live, fresh-only analysis of a real, popular
    title must return reviews and a Context Pack in seconds — proving the product
    needs no pre-seed. Uses the REAL Hardcover API + REAL local models."""
    token = get_settings().hardcover_api_token
    client = HardcoverClient(token=token)
    try:
        result = await analyze_live(
            title="Atomic Habits", hardcover=client,
            embedder=Embedder(), labeler=AspectLabeler(), seeded_clusters=None)
    finally:
        await client.aclose()

    assert result.get("not_found") is not True, "Hardcover did not resolve a known title"
    assert result["review_count"] > 0, "no live reviews returned"
    assert "candidates" in result["pack"]
    assert result["fresh_only"] is True
    # Provenance honesty: fresh-only must be flagged incomplete in the pack.
    assert result["pack"]["candidates"][0]["validity"]["incomplete"] is True
