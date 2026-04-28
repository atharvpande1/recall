import unittest

from src.resources.exceptions import UnsupportedResourceUrlError
from src.resources.types import ResourceType
from src.resources.utils import get_resource_type


class ResourceUtilsTests(unittest.TestCase):
    def test_get_resource_type_for_reddit(self) -> None:
        self.assertEqual(get_resource_type("https://www.reddit.com/r/python/"), ResourceType.REDDIT)

    def test_get_resource_type_for_web(self) -> None:
        self.assertEqual(get_resource_type("https://example.com/article"), ResourceType.WEB)

    def test_get_resource_type_rejects_youtube(self) -> None:
        with self.assertRaises(UnsupportedResourceUrlError):
            get_resource_type("https://youtu.be/dQw4w9WgXcQ")

    def test_get_resource_type_rejects_instagram(self) -> None:
        with self.assertRaises(UnsupportedResourceUrlError):
            get_resource_type("https://www.instagram.com/reel/abc123/")

    def test_get_resource_type_rejects_twitter(self) -> None:
        with self.assertRaises(UnsupportedResourceUrlError):
            get_resource_type("https://x.com/someuser/status/123")
