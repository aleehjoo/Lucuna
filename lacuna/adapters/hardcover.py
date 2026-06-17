# lacuna/adapters/hardcover.py
from __future__ import annotations

import httpx
from pydantic import BaseModel

from lacuna.adapters._http import RateLimiter, USER_AGENT, request_with_backoff
from lacuna.schemas.sources import HardcoverReview

ENDPOINT = "https://api.hardcover.app/v1/graphql"

_BOOK_BY_TITLE = """
query BookByTitle($q: String!) {
  books(where: {title: {_ilike: $q}}, limit: 1) {
    id
    title
    reviews { id rating body user_id created_at }
  }
}
"""


class HardcoverBook(BaseModel):
    id: int
    title: str
    reviews: list[HardcoverReview] = []


class HardcoverClient:
    def __init__(self, token: str, *, timeout: float = 30.0):
        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers={"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT},
        )
        self._limiter = RateLimiter(per_minute=60)

    async def _query(self, query: str, variables: dict) -> dict:
        resp = await request_with_backoff(
            self._client, "POST", ENDPOINT,
            json={"query": query, "variables": variables},
            limiter=self._limiter,
        )
        payload = resp.json()
        if "errors" in payload:
            raise RuntimeError(f"Hardcover GraphQL error: {payload['errors']}")
        return payload["data"]

    async def fetch_book_by_title(self, title: str) -> HardcoverBook | None:
        data = await self._query(_BOOK_BY_TITLE, {"q": f"%{title}%"})
        books = data.get("books") or []
        return HardcoverBook.model_validate(books[0]) if books else None

    async def aclose(self) -> None:
        await self._client.aclose()
