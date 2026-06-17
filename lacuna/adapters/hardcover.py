# lacuna/adapters/hardcover.py
from __future__ import annotations

import httpx
from pydantic import BaseModel

from lacuna.adapters._http import RateLimiter, USER_AGENT, request_with_backoff
from lacuna.schemas.sources import HardcoverReview

ENDPOINT = "https://api.hardcover.app/v1/graphql"

# Hardcover blocks `_ilike` ("ilike and related operations are not permitted on this
# server"), so fuzzy title→id resolution goes through the Typesense-backed `search`
# query, which returns the canonical edition (highest read/rating counts).
_SEARCH_BOOK = """
query SearchBook($q: String!) {
  search(query: $q, query_type: "Book", per_page: 5, page: 1) {
    results
  }
}
"""

# There is NO `reviews` relationship on `books`; live reviews live in `user_books`
# (text = `review_raw`, date = `reviewed_at`).
_REVIEWS_BY_BOOK = """
query ReviewsByBook($book_id: Int!, $limit: Int!) {
  user_books(
    where: {book_id: {_eq: $book_id}, has_review: {_eq: true}}
    order_by: {reviewed_at: desc_nulls_last}
    limit: $limit
  ) {
    id
    rating
    review_raw
    reviewed_at
    user_id
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

    @staticmethod
    def _best_hit(search_data: dict) -> dict | None:
        """Pick the canonical book from a `search` payload: the hit with the most
        readers (Typesense ranks by relevance, but the canonical edition is the most
        read — edition stubs share the title with 0 reads)."""
        results = (search_data.get("search") or {}).get("results") or {}
        hits = results.get("hits") or []
        docs = [h.get("document") or {} for h in hits]
        docs = [d for d in docs if d.get("id") is not None]
        if not docs:
            return None
        return max(docs, key=lambda d: d.get("users_read_count") or 0)

    async def fetch_reviews(self, book_id: int, *, limit: int = 50) -> list[HardcoverReview]:
        data = await self._query(_REVIEWS_BY_BOOK, {"book_id": int(book_id), "limit": limit})
        rows = data.get("user_books") or []
        return [HardcoverReview.from_user_book(r) for r in rows]

    async def fetch_book_by_title(self, title: str, *, review_limit: int = 50) -> HardcoverBook | None:
        search_data = await self._query(_SEARCH_BOOK, {"q": title})
        doc = self._best_hit(search_data)
        if doc is None:
            return None
        book_id = int(doc["id"])
        reviews = await self.fetch_reviews(book_id, limit=review_limit)
        return HardcoverBook(id=book_id, title=doc.get("title") or title, reviews=reviews)

    async def aclose(self) -> None:
        await self._client.aclose()
