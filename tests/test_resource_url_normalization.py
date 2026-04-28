import unittest

from src.exceptions import InvalidResourceUrlError
from src.resources.dependencies import normalize_resource_url


class NormalizeResourceUrlTests(unittest.TestCase):
    def test_filters_tracking_and_fragment(self) -> None:
        result = normalize_resource_url(
            "HTTP://WWW.Example.COM//Some%20Path/?utm_source=google&a=1&fbclid=abc#Section-1"
        )

        self.assertEqual(result["normalized_url"], "https://example.com/Some%20Path?a=1")
        self.assertEqual(
            result["tracking_query_params"],
            {"utm_source": ["google"], "fbclid": ["abc"]},
        )
        self.assertEqual(result["fragment"], "Section-1")

    def test_keeps_unknown_query_params(self) -> None:
        result = normalize_resource_url(
            "https://example.com/path?tag=python&tag=fastapi&utm_medium=email"
        )

        self.assertEqual(
            result["normalized_url"], "https://example.com/path?tag=python&tag=fastapi"
        )
        self.assertEqual(result["tracking_query_params"], {"utm_medium": ["email"]})
        self.assertIsNone(result["fragment"])

    def test_preserves_encoded_path_segments(self) -> None:
        result = normalize_resource_url("https://example.com/a%2Fb")

        self.assertEqual(result["normalized_url"], "https://example.com/a%2Fb")

    def test_accepts_localhost_without_www(self) -> None:
        result = normalize_resource_url("localhost:8000/path")

        self.assertEqual(result["normalized_url"], "https://localhost:8000/path")

    def test_rejects_invalid_url(self) -> None:
        with self.assertRaises(InvalidResourceUrlError) as ctx:
            normalize_resource_url("http://exa mple.com")

        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIsInstance(ctx.exception.detail, list)
        self.assertGreater(len(ctx.exception.detail), 0)
        first_error = ctx.exception.detail[0]
        self.assertEqual(first_error["type"], "url_parsing")
        self.assertEqual(first_error["loc"], ["query", "resource_url"])
        self.assertEqual(
            first_error["msg"],
            "Input should be a valid URL, invalid international domain name",
        )
        self.assertEqual(first_error["input"], "http://exa mple.com")

    def test_rejects_plain_text_input(self) -> None:
        with self.assertRaises(InvalidResourceUrlError) as ctx:
            normalize_resource_url("just some text")

        self.assertEqual(ctx.exception.status_code, 422)
        first_error = ctx.exception.detail[0]
        self.assertEqual(first_error["type"], "url_parsing")
        self.assertEqual(first_error["loc"], ["query", "resource_url"])
        self.assertEqual(
            first_error["msg"],
            "Input should be a valid URL, invalid international domain name",
        )
        self.assertEqual(first_error["input"], "https://just some text")

    def test_accepts_intranet_host_without_dot(self) -> None:
        result = normalize_resource_url("intranet/path")

        self.assertEqual(result["normalized_url"], "https://intranet/path")
