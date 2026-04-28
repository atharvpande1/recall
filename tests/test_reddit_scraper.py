import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

import httpx

from src.resources.scrapers.reddit import RedditScraper
from src.resources.types import RedditPostType, RedditUrlType


class RedditScraperTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scraper = RedditScraper(client=httpx.AsyncClient())

    def tearDown(self) -> None:
        import asyncio

        asyncio.run(self.scraper.client.aclose())

    def test_detect_url_type_for_post(self) -> None:
        self.assertEqual(
            self.scraper._detect_url_type("https://www.reddit.com/r/python/comments/abc123/example_post/"),
            RedditUrlType.POST,
        )

    def test_detect_url_type_for_subreddit(self) -> None:
        self.assertEqual(
            self.scraper._detect_url_type("https://www.reddit.com/r/python/"),
            RedditUrlType.SUBREDDIT,
        )

    def test_detect_url_type_for_user_profile(self) -> None:
        self.assertEqual(
            self.scraper._detect_url_type("https://www.reddit.com/u/example_user/"),
            RedditUrlType.USER_PROFILE,
        )
        self.assertEqual(
            self.scraper._detect_url_type("https://www.reddit.com/user/example_user/"),
            RedditUrlType.USER_PROFILE,
        )

    def test_detect_url_type_for_unknown(self) -> None:
        self.assertEqual(
            self.scraper._detect_url_type("https://www.reddit.com/"),
            RedditUrlType.UNKNOWN,
        )

    def test_parse_post_response_filters_to_top_three_natural_comments(self) -> None:
        response = [
            {
                "data": {
                    "children": [
                        {
                            "data": {
                                "id": "post1",
                                "title": "Example post",
                            }
                        }
                    ]
                }
            },
            {
                "data": {
                    "children": [
                        {"kind": "t1", "data": {"author": "first_user", "body": "First", "distinguished": None}},
                        {"kind": "t1", "data": {"author": "AutoModerator", "body": "Bot comment", "distinguished": None}},
                        {"kind": "t1", "data": {"author": "mod_user", "body": "Mod comment", "distinguished": "moderator"}},
                        {"kind": "t1", "data": {"author": "second_user", "body": "Second", "distinguished": None}},
                        {"kind": "t1", "data": {"author": "third_bot", "body": "Bot comment", "distinguished": None}},
                        {"kind": "t1", "data": {"author": "fourth_user", "body": "Fourth", "distinguished": None}},
                        {"kind": "more", "data": {}},
                        {"kind": "t1", "data": {"author": "[deleted]", "body": "[removed]", "distinguished": None}},
                    ]
                }
            },
        ]

        post, comments = self.scraper._parse_post_response(response)

        self.assertEqual(post["id"], "post1")
        self.assertEqual([c["author"] for c in comments], ["first_user", "second_user", "fourth_user"])
        self.assertEqual(len(comments), 3)

    def test_scrape_post_delegates_video_keyframes_to_media_service(self) -> None:
        media_service = AsyncMock()
        media_service.extract_and_describe_keyframes = AsyncMock(return_value=[])
        scraper = RedditScraper(
            client=self.scraper.client,
            media_service=media_service,
        )
        scraper.fetch_json = AsyncMock(
            return_value=[
                {
                    "data": {
                        "children": [
                            {
                                "data": {
                                    "name": "t3_post1",
                                    "title": "Video post",
                                    "url": "https://v.redd.it/example",
                                    "domain": "v.redd.it",
                                    "post_hint": "hosted:video",
                                    "selftext": "",
                                    "subreddit_name_prefixed": "r/python",
                                    "num_comments": 4,
                                    "permalink": "/r/python/comments/post1/video_post/",
                                    "media": {
                                        "reddit_video": {
                                            "fallback_url": "https://v.redd.it/example/DASH_720.mp4",
                                            "duration": 35,
                                        }
                                    },
                                }
                            }
                        ]
                    }
                },
                {"data": {"children": []}},
            ]
        )
        scraper._get_post_type = MagicMock(return_value=RedditPostType.VIDEO)

        asyncio.run(scraper.scrape_post("https://www.reddit.com/r/python/comments/post1/video_post/"))

        media_service.extract_and_describe_keyframes.assert_awaited_once()
