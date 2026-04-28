import asyncio
import unittest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from src.resources.scrapers.youtube import YoutubeScraper
from src.resources.types import (
    YoutubeChannelMetadata,
    YoutubePlaylistMetadata,
    YoutubeUrlType,
    YoutubeVideoMetadata,
    VideoTranscript,
)
from src.resources.utils import classify_youtube_url


def _make_ydl_mock(info: dict) -> MagicMock:
    ydl = MagicMock()
    ydl.__enter__.return_value = ydl
    ydl.extract_info.return_value = info
    return ydl


class YoutubeScraperTests(unittest.TestCase):
    def test_get_yt_metadata_returns_playlist_metadata(self) -> None:
        client = httpx.AsyncClient()
        try:
            scraper = YoutubeScraper(client=client)
            fake_info = {
                "id": "playlist-id",
                "webpage_url": "https://www.youtube.com/playlist?list=PL123",
                "title": "  Playlist Title  ",
                "description": "",
                "modified_date": "20240102",
                "tags": ["tag1", "", "  tag2  "],
                "thumbnail": "",
                "playlist_count": 2,
                "channel_id": "chan123",
                "channel": "Channel Name",
                "channel_url": "https://www.youtube.com/@channel",
                "uploader_id": "upl123",
                "uploader": "Uploader Name",
                "uploader_url": "",
                "entries": [
                    {
                        "id": "video-1",
                        "webpage_url": "https://www.youtube.com/watch?v=video-1",
                        "title": "Video 1",
                        "description": "",
                        "thumbnail": "",
                        "uploader": "",
                        "uploader_id": "",
                        "channel_url": "",
                        "upload_date": "20240101",
                        "modified_date": "",
                        "formats": [],
                        "duration": "123",
                        "language": "en",
                        "categories": ["Education", ""],
                        "tags": ["tag1", ""],
                        "chapters": [],
                        "view_count": "10",
                        "like_count": "2",
                        "comment_count": "1",
                        "age_limit": 0,
                        "is_live": False,
                        "was_live": False,
                    }
                ],
            }

            youtube_dl_instance = _make_ydl_mock(fake_info)

            with patch("src.resources.scrapers.youtube.yt_dlp.YoutubeDL", return_value=youtube_dl_instance) as ydl_cls:
                metadata = scraper.get_yt_metadata(
                    "https://www.youtube.com/playlist?list=PL123",
                    yt_type=YoutubeUrlType.PLAYLIST,
                )

            self.assertIsInstance(metadata, YoutubePlaylistMetadata)
            self.assertEqual(metadata.id, "playlist-id")
            self.assertEqual(metadata.title, "Playlist Title")
            self.assertIsNone(metadata.description)
            self.assertIsNone(metadata.thumbnail_url)
            self.assertEqual(metadata.tags, ["tag1", "tag2"])
            self.assertEqual(metadata.video_count, 2)
            self.assertEqual(metadata.modified_date, datetime(2024, 1, 2))
            self.assertEqual(metadata.channel_name, "Channel Name")
            self.assertEqual(metadata.uploader_name, "Uploader Name")
            self.assertEqual(len(metadata.entries), 1)
            self.assertIsInstance(metadata.entries[0], YoutubeVideoMetadata)
            self.assertIsNone(metadata.entries[0].description)
            self.assertIsNone(metadata.entries[0].thumbnail)
            self.assertEqual(metadata.entries[0].duration, 123)
            self.assertEqual(metadata.entries[0].categories, ["Education"])
            self.assertEqual(metadata.entries[0].tags, ["tag1"])
            self.assertEqual(metadata.entries[0].view_count, 10)
            self.assertEqual(metadata.entries[0].like_count, 2)
            self.assertEqual(metadata.entries[0].comment_count, 1)
            self.assertEqual(ydl_cls.call_args.args[0]["extract_flat"], "in_playlist")
            self.assertEqual(ydl_cls.call_args.args[0]["playlistend"], 10)
        finally:
            asyncio.run(client.aclose())

    def test_get_yt_metadata_returns_channel_metadata(self) -> None:
        client = httpx.AsyncClient()
        try:
            scraper = YoutubeScraper(client=client)
            fake_info = {
                "id": "channel-id",
                "webpage_url": "https://www.youtube.com/@channel",
                "title": "  Channel Title  ",
                "description": "",
                "thumbnail": "",
                "channel": "  Channel Name  ",
                "uploader": "Uploader Name",
                "uploader_id": "upl123",
                "channel_url": "https://www.youtube.com/@channel",
                "uploader_url": "",
                "channel_follower_count": "4567",
            }

            youtube_dl_instance = _make_ydl_mock(fake_info)

            with patch("src.resources.scrapers.youtube.yt_dlp.YoutubeDL", return_value=youtube_dl_instance) as ydl_cls:
                metadata = scraper.get_yt_metadata(
                    "https://www.youtube.com/@channel",
                    yt_type=YoutubeUrlType.CHANNEL,
                )

            self.assertIsInstance(metadata, YoutubeChannelMetadata)
            self.assertEqual(metadata.id, "channel-id")
            self.assertEqual(metadata.title, "Channel Title")
            self.assertEqual(metadata.channel_name, "Channel Name")
            self.assertEqual(metadata.uploader_name, "Uploader Name")
            self.assertEqual(metadata.uploader_id, "upl123")
            self.assertEqual(metadata.subscriber_count, 4567)
            self.assertIsNone(metadata.description)
            self.assertIsNone(metadata.thubmnail_url)
            self.assertEqual(ydl_cls.call_args.args[0]["extract_flat"], True)
            self.assertEqual(ydl_cls.call_args.args[0]["playlistend"], 0)
        finally:
            asyncio.run(client.aclose())

    def test_classify_youtube_url_treats_extra_params_as_video(self) -> None:
        self.assertEqual(
            classify_youtube_url("https://www.youtube.com/watch?v=abc123&si=xyz&feature=share"),
            YoutubeUrlType.VIDEO,
        )

    def test_scrape_video_delegates_keyframe_enrichment_to_media_service(self) -> None:
        client = httpx.AsyncClient()
        try:
            media_service = AsyncMock()
            media_service.extract_and_describe_keyframes = AsyncMock(return_value=[])
            scraper = YoutubeScraper(client=client, media_service=media_service)
            scraper.get_yt_metadata = MagicMock(
                return_value=YoutubeVideoMetadata(
                    id="video1",
                    url="https://www.youtube.com/watch?v=video1",
                    title="Video Title",
                    description=None,
                    thumbnail=None,
                    type=YoutubeUrlType.VIDEO,
                    uploader=None,
                    uploader_id=None,
                    channel_url=None,
                    upload_date=None,
                    modified_date=None,
                    worst_quality_url="https://cdn.example/video.mp4",
                    duration=60,
                    language="en",
                    categories=["Education"],
                    tags=["tag1"],
                    chapters=None,
                    view_count=None,
                    like_count=None,
                    comment_count=None,
                    is_short=False,
                    age_restricted=False,
                    is_live=False,
                )
            )
            scraper._get_transcipt_by_video_id = AsyncMock(
                return_value=[
                    VideoTranscript(
                        id="video1",
                        segments=[],
                        full_text="Transcript",
                        language="en",
                        category="Education",
                    )
                ]
            )

            asyncio.run(scraper.scrape_video("https://www.youtube.com/watch?v=video1"))

            media_service.extract_and_describe_keyframes.assert_awaited_once()
        finally:
            asyncio.run(client.aclose())
