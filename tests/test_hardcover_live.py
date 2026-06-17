# tests/test_hardcover_live.py
import os
import pytest
from lacuna.config import get_settings
from lacuna.adapters.hardcover import HardcoverClient
from lacuna.pipeline.validation import validate_hardcover

pytestmark = pytest.mark.skipif(
    not os.getenv("HARDCOVER_API_TOKEN"),
    reason="HARDCOVER_API_TOKEN not set — live gate skipped",
)

async def test_hardcover_returns_live_reviews_for_known_title():
    token = get_settings().hardcover_api_token
    client = HardcoverClient(token=token)
    try:
        res = await validate_hardcover(client, sample_title="Atomic Habits", recorder=None)
    finally:
        await client.aclose()
    assert res.passed, f"G0 gate failed: {res.error}"
    assert res.review_count > 0
