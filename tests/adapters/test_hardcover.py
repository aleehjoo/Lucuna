# tests/adapters/test_hardcover.py
import httpx, respx
from lacuna.adapters.hardcover import HardcoverClient

RECORDED = {
  "data": {"books": [{
      "id": 42, "title": "Meditations",
      "reviews": [
        {"id": 1, "rating": 2.0, "body": "translation is clunky", "user_id": 5, "created_at": "2025-01-02T00:00:00Z"},
        {"id": 2, "rating": 5.0, "body": "great", "user_id": 6, "created_at": "2025-02-02T00:00:00Z"},
      ],
  }]}
}

@respx.mock
async def test_fetch_reviews_by_title_parses_recorded():
    respx.post("https://api.hardcover.app/v1/graphql").mock(
        return_value=httpx.Response(200, json=RECORDED))
    client = HardcoverClient(token="eyJ-fake")
    book = await client.fetch_book_by_title("Meditations")
    assert book.title == "Meditations"
    assert len(book.reviews) == 2
    assert book.reviews[0].body == "translation is clunky"
    await client.aclose()

@respx.mock
async def test_auth_header_has_no_double_bearer():
    captured = {}
    def _capture(request):
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"data": {"books": []}})
    respx.post("https://api.hardcover.app/v1/graphql").mock(side_effect=_capture)
    client = HardcoverClient(token="eyJ-fake")
    await client.fetch_book_by_title("x")
    assert captured["auth"] == "Bearer eyJ-fake"
    await client.aclose()
