# tests/adapters/test_open_library.py
import httpx, respx
from lacuna.adapters.open_library import OpenLibraryClient

RECORDED = {"numFound": 2, "docs": [
    {"title": "Stoic Daily", "first_publish_year": 2024, "edition_count": 3},
    {"title": "On Discipline", "first_publish_year": 2018, "edition_count": 1},
]}

@respx.mock
async def test_subject_search_counts_recent_titles():
    respx.get(url__startswith="https://openlibrary.org/search.json").mock(
        return_value=httpx.Response(200, json=RECORDED))
    client = OpenLibraryClient()
    result = await client.subject_search("stoicism", cutoff_year=2023)
    assert result.title_count == 2
    assert result.recent_title_count == 1   # only the 2024 title is post-cutoff
    await client.aclose()
