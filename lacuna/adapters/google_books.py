# lacuna/adapters/google_books.py
from __future__ import annotations

import httpx

from lacuna.adapters._http import RateLimiter, request_with_backoff
from lacuna.schemas.sources import GoogleVolume

BASE = "https://www.googleapis.com/books/v1/volumes"


class GoogleBooksClient:
    def __init__(self, api_key: str):
        self._client = httpx.AsyncClient(timeout=20.0)
        self._key = api_key
        self._limiter = RateLimiter(per_minute=60)  # well under ~1000/day

    async def search(self, query: str, *, max_results: int = 20) -> list[GoogleVolume]:
        resp = await request_with_backoff(
            self._client, "GET", BASE,
            params={"q": query, "maxResults": max_results, "key": self._key},
            limiter=self._limiter,
        )
        items = resp.json().get("items", [])
        return [GoogleVolume.model_validate(it) for it in items]

    async def aclose(self) -> None:
        await self._client.aclose()
