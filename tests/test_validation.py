# tests/test_validation.py
import pytest
from lacuna.pipeline.validation import validate_hardcover, ValidationResult

class FakeBook:
    def __init__(self, title, reviews): self.title = title; self.reviews = reviews

class FakeClient:
    def __init__(self, book): self._book = book
    async def fetch_book_by_title(self, title): return self._book
    async def aclose(self): pass

async def test_gate_passes_when_reviews_present():
    recorded = []
    async def recorder(res): recorded.append(res)
    client = FakeClient(FakeBook("Atomic Habits", [object(), object(), object()]))
    res = await validate_hardcover(client, sample_title="Atomic Habits", recorder=recorder)
    assert isinstance(res, ValidationResult)
    assert res.passed is True and res.review_count == 3
    assert recorded and recorded[0].passed is True

async def test_gate_fails_when_no_reviews():
    client = FakeClient(FakeBook("Atomic Habits", []))
    res = await validate_hardcover(client, sample_title="Atomic Habits", recorder=None)
    assert res.passed is False and res.review_count == 0

async def test_gate_fails_when_title_not_found():
    client = FakeClient(None)
    res = await validate_hardcover(client, sample_title="Nonexistent", recorder=None)
    assert res.passed is False and res.error is not None
