# lacuna/adapters/open_library.py
from __future__ import annotations

import httpx
from pydantic import BaseModel

from lacuna.adapters._http import RateLimiter, request_with_backoff
from lacuna.schemas.sources import OpenLibraryDoc

BASE = "https://openlibrary.org/search.json"


class SupplyResult(BaseModel):
    title_count: int
    recent_title_count: int


class OpenLibraryClient:
    def __init__(self):
        self._client = httpx.AsyncClient(timeout=30.0)
        self._limiter = RateLimiter(per_minute=60)  # be polite

    async def subject_search(self, subject: str, *, cutoff_year: int = 2023,
                             limit: int = 100) -> SupplyResult:
        resp = await request_with_backoff(
            self._client, "GET", BASE,
            params={"q": f"subject:{subject}", "limit": limit,
                    "fields": "title,first_publish_year,edition_count"},
            limiter=self._limiter,
        )
        payload = resp.json()
        docs = [OpenLibraryDoc.model_validate(d) for d in payload.get("docs", [])]
        recent = sum(1 for d in docs if (d.first_publish_year or 0) > cutoff_year)
        return SupplyResult(title_count=payload.get("numFound", len(docs)),
                            recent_title_count=recent)

    async def aclose(self) -> None:
        await self._client.aclose()
