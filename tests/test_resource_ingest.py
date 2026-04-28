import unittest
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import httpx

from src.exceptions import ResourceResolutionError
from src.resources.exceptions import UnsupportedResourceUrlError
from src.resources.ingest import IngestResource
from src.resources.scrapers.base import ScrapeResult
from src.resources.scrapers.reddit import RedditScraper
from src.resources.scrapers.web import WebScraper
from src.resources.types import ResourceType


class IngestResourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ingest = IngestResource()

    def test_get_extractor_for_reddit_com_url(self) -> None:
        scraper = self.ingest._get_extractor_for_url("https://www.reddit.com/r/python/")

        self.assertIsInstance(scraper, RedditScraper)

    def test_get_extractor_for_redd_it_url(self) -> None:
        scraper = self.ingest._get_extractor_for_url("https://redd.it/abc123")

        self.assertIsInstance(scraper, RedditScraper)

    def test_get_extractor_for_non_reddit_url(self) -> None:
        scraper = self.ingest._get_extractor_for_url("https://example.com/article")

        self.assertIsInstance(scraper, WebScraper)

    def test_get_extractor_for_reddit_lookalike_domain(self) -> None:
        extractor = self.ingest._get_extractor_for_url("https://notreddit.com/article")

        self.assertIsInstance(extractor, WebScraper)

    def test_get_extractor_for_x_lookalike_domain(self) -> None:
        extractor = self.ingest._get_extractor_for_url("https://maliciousx.com/article")

        self.assertIsInstance(extractor, WebScraper)

    def test_get_extractor_for_youtube_url(self) -> None:
        for url in [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://m.youtube.com/watch?v=dQw4w9WgXcQ",
        ]:
            with self.subTest(url=url):
                with self.assertRaises(UnsupportedResourceUrlError) as ctx:
                    self.ingest._get_extractor_for_url(url)

                self.assertEqual(ctx.exception.status_code, 422)
                self.assertIn("YouTube", ctx.exception.detail[0]["msg"])

    def test_get_extractor_for_instagram_url(self) -> None:
        for url in [
            "https://www.instagram.com/reel/abc123/",
            "https://instagram.com/reel/abc123/",
            "https://mobile.instagram.com/reel/abc123/",
        ]:
            with self.subTest(url=url):
                with self.assertRaises(UnsupportedResourceUrlError) as ctx:
                    self.ingest._get_extractor_for_url(url)

                self.assertEqual(ctx.exception.status_code, 422)
                self.assertIn("Instagram", ctx.exception.detail[0]["msg"])

    def test_get_extractor_for_twitter_url(self) -> None:
        for url in [
            "https://x.com/someuser/status/123",
            "https://www.x.com/someuser/status/123",
            "https://twitter.com/someuser/status/123",
            "https://mobile.twitter.com/someuser/status/123",
        ]:
            with self.subTest(url=url):
                with self.assertRaises(UnsupportedResourceUrlError) as ctx:
                    self.ingest._get_extractor_for_url(url)

                self.assertEqual(ctx.exception.status_code, 422)
                self.assertIn("Twitter/X", ctx.exception.detail[0]["msg"])

    def test_extract_propagates_unsupported_resource_error(self) -> None:
        self.ingest.client = httpx.AsyncClient()
        self.ingest._resolve_destination_url = AsyncMock(return_value="https://www.youtube.com/watch?v=dQw4w9WgXcQ")

        with self.assertRaises(UnsupportedResourceUrlError):
            import asyncio

            asyncio.run(self.ingest.extract(url="https://example.com"))
        import asyncio
        asyncio.run(self.ingest.client.aclose())

    def test_extract_returns_scrape_result(self) -> None:
        class FakeScraper:
            async def scrape(self, url: str, *, fragment, tracking_query_params):
                return ScrapeResult(
                    source_type=ResourceType.WEB,
                    canonical_url=url,
                    title="title",
                    content_text="content",
                    metadata={},
                )

        self.ingest.client = httpx.AsyncClient()
        self.ingest._resolve_destination_url = AsyncMock(return_value="https://example.com/article")
        self.ingest._get_extractor_for_url = MagicMock(return_value=FakeScraper())

        import asyncio

        result = asyncio.run(self.ingest.extract(url="https://example.com/article"))
        self.assertIsInstance(result, ScrapeResult)
        self.assertEqual(result.canonical_url, "https://example.com/article")
        asyncio.run(self.ingest.client.aclose())

    def test_resolve_destination_url_wraps_transport_errors(self) -> None:
        class FakeClient:
            def __init__(self):
                self.is_closed = False

            async def aclose(self):
                self.is_closed = True

            async def head(self, url: str):
                raise httpx.RequestError("boom", request=httpx.Request("HEAD", url))

        self.ingest.client = FakeClient()
        with patch("src.resources.ingest.httpx.AsyncClient", return_value=FakeClient()):
            with self.assertRaises(ResourceResolutionError) as ctx:
                import asyncio

                asyncio.run(self.ingest._resolve_destination_url("https://example.com"))

        self.assertEqual(ctx.exception.status_code, 502)
        self.assertEqual(ctx.exception.detail[0]["type"], "resource_resolution_failed")
