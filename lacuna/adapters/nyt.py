# lacuna/adapters/nyt.py
from __future__ import annotations

import httpx

from lacuna.adapters._http import RateLimiter, request_with_backoff
from lacuna.schemas.sources import NytBestseller

BASE = "https://api.nytimes.com/svc/books/v3/lists/current"


class NytClient:
    def __init__(self, api_key: str):
        self._client = httpx.AsyncClient(timeout=20.0)
        self._key = api_key
        self._limiter = RateLimiter(per_minute=10)  # PRD §4

    async def current_list(self, list_name: str) -> list[NytBestseller]:
        resp = await request_with_backoff(
            self._client, "GET", f"{BASE}/{list_name}.json",
            params={"api-key": self._key}, limiter=self._limiter,
        )
        books = resp.json().get("results", {}).get("books", [])
        return [NytBestseller.model_validate(b) for b in books]

    async def aclose(self) -> None:
        await self._client.aclose()
