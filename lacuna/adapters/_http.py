# lacuna/adapters/_http.py
from __future__ import annotations

import asyncio
import random
import time

import httpx

USER_AGENT = "Lacuna/0.1 (reader-gap research; +https://github.com/lacuna)"
RETRY_STATUS = {429, 500, 502, 503, 504}


class RateLimiter:
    """Simple async min-interval limiter (token spacing)."""
    def __init__(self, per_minute: int):
        self._interval = 60.0 / per_minute
        self._last = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            wait = self._interval - (now - self._last)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = time.monotonic()


async def request_with_backoff(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    max_attempts: int = 5,
    base_delay: float = 0.5,
    limiter: RateLimiter | None = None,
    **kwargs,
) -> httpx.Response:
    """Issue a request, retrying RETRY_STATUS with exponential backoff + jitter,
    honoring Retry-After. Raises httpx.HTTPStatusError on terminal failure."""
    headers = {"User-Agent": USER_AGENT, **kwargs.pop("headers", {})}
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        if limiter:
            await limiter.acquire()
        resp = await client.request(method, url, headers=headers, **kwargs)
        if resp.status_code in RETRY_STATUS and attempt < max_attempts:
            retry_after = resp.headers.get("Retry-After")
            delay = float(retry_after) if retry_after and retry_after.isdigit() \
                else base_delay * (2 ** (attempt - 1)) + random.uniform(0, base_delay)
            await asyncio.sleep(delay)
            last_exc = httpx.HTTPStatusError("retryable", request=resp.request, response=resp)
            continue
        resp.raise_for_status()
        return resp
    assert last_exc is not None
    raise last_exc
