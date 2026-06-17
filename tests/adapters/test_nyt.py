# tests/adapters/test_nyt.py
import httpx, respx
from lacuna.adapters.nyt import NytClient

RECORDED = {"results": {"books": [
    {"title": "ATOMIC HABITS", "weeks_on_list": 250, "rank": 1},
    {"title": "THE LET THEM THEORY", "weeks_on_list": 5, "rank": 2},
]}}

@respx.mock
async def test_list_bestsellers_parses():
    respx.get(url__startswith="https://api.nytimes.com/svc/books/v3/lists/current").mock(
        return_value=httpx.Response(200, json=RECORDED))
    client = NytClient(api_key="k")
    rows = await client.current_list("advice-how-to-and-miscellaneous")
    assert rows[0].title == "ATOMIC HABITS" and rows[0].weeks_on_list == 250
    await client.aclose()
