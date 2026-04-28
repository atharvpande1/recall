from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

import httpx


def build_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        follow_redirects=True,
        max_redirects=10,
        timeout=httpx.Timeout(10.0, connect=5.0),
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        },
    )


@asynccontextmanager
async def http_client_context() -> AsyncIterator[httpx.AsyncClient]:
    client = build_http_client()
    try:
        yield client
    finally:
        await client.aclose()
