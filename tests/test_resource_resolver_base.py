import unittest

import httpx

from src.resources.scrapers.base import BaseScraper, ScrapeResult
from src.resources.types import ResourceType


class DummyScraper(BaseScraper):
    async def scrape(
        self,
        url: str,
        *,
        fragment: str | None = None,
        tracking_query_params: dict[str, list[str]] | None = None,
    ) -> ScrapeResult:
        return ScrapeResult(
            source_type=ResourceType.WEB,
            canonical_url=url,
            title=None,
            content_text="dummy",
            metadata={},
        )


class BaseResolverTests(unittest.IsolatedAsyncioTestCase):
    async def test_async_context_creates_and_closes_owned_client(self) -> None:
        async with DummyScraper() as resolver:
            self.assertIsInstance(resolver.client, httpx.AsyncClient)
            self.assertFalse(resolver.client.is_closed)

        self.assertTrue(resolver.client.is_closed)

    async def test_async_context_does_not_close_injected_client(self) -> None:
        injected_client = httpx.AsyncClient()
        async with DummyScraper(client=injected_client) as resolver:
            self.assertIs(resolver.client, injected_client)
            self.assertFalse(injected_client.is_closed)

        self.assertFalse(injected_client.is_closed)
        await injected_client.aclose()

    async def test_child_resolver_works_as_async_context_manager(self) -> None:
        async with DummyScraper() as resolver:
            self.assertIsInstance(resolver, DummyScraper)
            self.assertIsInstance(resolver.client, httpx.AsyncClient)
