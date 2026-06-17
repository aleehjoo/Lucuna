# tests/adapters/test_http.py
import httpx, respx, pytest
from lacuna.adapters._http import request_with_backoff, RateLimiter

@respx.mock
async def test_retries_on_429_then_succeeds():
    route = respx.get("https://x.test/a")
    route.side_effect = [
        httpx.Response(429, headers={"Retry-After": "0"}),
        httpx.Response(200, json={"ok": True}),
    ]
    async with httpx.AsyncClient() as c:
        resp = await request_with_backoff(c, "GET", "https://x.test/a", max_attempts=3)
    assert resp.status_code == 200
    assert route.call_count == 2

@respx.mock
async def test_gives_up_and_raises_after_max_attempts():
    respx.get("https://x.test/b").mock(return_value=httpx.Response(503))
    async with httpx.AsyncClient() as c:
        with pytest.raises(httpx.HTTPStatusError):
            await request_with_backoff(c, "GET", "https://x.test/b", max_attempts=2, base_delay=0)

async def test_rate_limiter_spaces_calls():
    import time
    rl = RateLimiter(per_minute=600)  # 0.1s spacing
    t0 = time.monotonic()
    await rl.acquire(); await rl.acquire()
    assert time.monotonic() - t0 >= 0.09
