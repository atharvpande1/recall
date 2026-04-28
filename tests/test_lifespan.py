import unittest
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

from fastapi import FastAPI

from src.lifespan import lifespan


class LifespanTests(unittest.IsolatedAsyncioTestCase):
    async def test_lifespan_yields_and_closes_shared_resources(self) -> None:
        app = FastAPI()
        fake_browser = AsyncMock()
        fake_playwright = MagicMock()
        fake_playwright.chromium.launch = AsyncMock(return_value=fake_browser)
        fake_playwright.stop = AsyncMock()
        fake_playwright_ctx = MagicMock()
        fake_playwright_ctx.start = AsyncMock(return_value=fake_playwright)

        with patch("src.lifespan.async_playwright", return_value=fake_playwright_ctx):
            async with lifespan(app) as state:
                self.assertIn("http_client", state)
                self.assertIn("browser", state)
                self.assertFalse(state["http_client"].is_closed)
                self.assertIs(state["browser"], fake_browser)

        self.assertTrue(state["http_client"].is_closed)
        fake_browser.close.assert_awaited_once()
        fake_playwright.stop.assert_awaited_once()
