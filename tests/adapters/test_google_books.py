# tests/adapters/test_google_books.py
import httpx, respx
from lacuna.adapters.google_books import GoogleBooksClient

RECORDED = {"items": [
    {"volumeInfo": {"title": "Discipline Is Destiny", "categories": ["Self-Help"],
                    "averageRating": 4.2, "ratingsCount": 250}},
]}

@respx.mock
async def test_search_volumes_parses_and_extracts_ratings():
    respx.get(url__startswith="https://www.googleapis.com/books/v1/volumes").mock(
        return_value=httpx.Response(200, json=RECORDED))
    client = GoogleBooksClient(api_key="k")
    vols = await client.search("stoicism")
    assert vols[0].ratings_count == 250
    assert vols[0].categories == ["Self-Help"]
    await client.aclose()
