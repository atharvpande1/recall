import unittest
from types import SimpleNamespace
from unittest.mock import patch

import httpx

from src.exceptions import MissingBrowserError
from src.exceptions import MissingHttpClientError
from src.resources.dependencies import get_browser
from src.resources.dependencies import get_http_client


class ResourceDependenciesTests(unittest.TestCase):
    def test_get_http_client_returns_async_client_from_request_state(self) -> None:
        client = httpx.AsyncClient()
        try:
            request = SimpleNamespace(state=SimpleNamespace(http_client=client))
            self.assertIs(get_http_client(request), client)
        finally:
            import asyncio

            asyncio.run(client.aclose())

    def test_get_http_client_raises_when_missing_or_invalid(self) -> None:
        request = SimpleNamespace(state=SimpleNamespace(http_client=None))
        with self.assertRaises(MissingHttpClientError) as ctx:
            get_http_client(request)

        self.assertEqual(ctx.exception.status_code, 500)
        self.assertEqual(ctx.exception.detail[0]["type"], "http_client_unavailable")

    def test_get_browser_returns_browser_from_request_state(self) -> None:
        class FakeBrowser:
            pass

        browser = FakeBrowser()
        request = SimpleNamespace(state=SimpleNamespace(browser=browser))
        with patch("src.resources.dependencies.Browser", FakeBrowser):
            self.assertIs(get_browser(request), browser)

    def test_get_browser_raises_when_missing_or_invalid(self) -> None:
        request = SimpleNamespace(state=SimpleNamespace(browser=None))
        with self.assertRaises(MissingBrowserError) as ctx:
            get_browser(request)

        self.assertEqual(ctx.exception.status_code, 500)
        self.assertEqual(ctx.exception.detail[0]["type"], "browser_unavailable")
