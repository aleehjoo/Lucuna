# tests/adapters/test_hardcover.py
import httpx, respx
from lacuna.adapters.hardcover import HardcoverClient

# Hardcover's `search` (Typesense) resolves title -> canonical book id; reviews then
# come from `user_books` (NOT a `reviews` relationship). These payloads mirror the
# live shapes confirmed against the API.
SEARCH = {
  "data": {"search": {"results": {"hits": [
      {"document": {"id": "490927", "title": "Atomic Habits", "users_read_count": 0}},
      {"document": {"id": "42", "title": "Meditations", "users_read_count": 100}},
  ]}}}
}
REVIEWS = {
  "data": {"user_books": [
      {"id": 1, "rating": 2.0, "review_raw": "translation is clunky", "reviewed_at": "2025-01-02T00:00:00Z", "user_id": 5},
      {"id": 2, "rating": 5.0, "review_raw": "great", "reviewed_at": "2025-02-02T00:00:00Z", "user_id": 6},
  ]}
}


def _router(request):
    body = request.content.decode()
    if "search" in body:
        return httpx.Response(200, json=SEARCH)
    return httpx.Response(200, json=REVIEWS)


@respx.mock
async def test_fetch_reviews_by_title_parses_recorded():
    respx.post("https://api.hardcover.app/v1/graphql").mock(side_effect=_router)
    client = HardcoverClient(token="eyJ-fake")
    book = await client.fetch_book_by_title("Meditations")
    # picks the canonical hit (most readers), not the empty edition stub
    assert book.id == 42
    assert book.title == "Meditations"
    assert len(book.reviews) == 2
    assert book.reviews[0].body == "translation is clunky"
    await client.aclose()


@respx.mock
async def test_auth_header_has_no_double_bearer():
    captured = {}
    def _capture(request):
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"data": {"search": {"results": {"hits": []}}}})
    respx.post("https://api.hardcover.app/v1/graphql").mock(side_effect=_capture)
    client = HardcoverClient(token="eyJ-fake")
    book = await client.fetch_book_by_title("x")
    assert book is None  # no hits -> no book
    assert captured["auth"] == "Bearer eyJ-fake"
    await client.aclose()
