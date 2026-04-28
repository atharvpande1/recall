import unittest

import httpx

from src.resources.http import build_http_client


class ResourceHttpTests(unittest.TestCase):
    def test_build_http_client_uses_central_defaults(self) -> None:
        client = build_http_client()
        try:
            self.assertIsInstance(client, httpx.AsyncClient)
            self.assertTrue(client.follow_redirects)
            self.assertEqual(client.max_redirects, 10)
            self.assertIn("Mozilla/5.0", client.headers["User-Agent"])
        finally:
            import asyncio

            asyncio.run(client.aclose())
