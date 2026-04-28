import asyncio
import unittest
from unittest.mock import AsyncMock

from google import genai

from src.resources.media.service import MediaEnrichmentService


class MediaEnrichmentServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gemini_client = AsyncMock(spec=genai.Client)
        self.service = MediaEnrichmentService(gemini_client=self.gemini_client)

    def test_extract_and_describe_keyframes_returns_descriptions(self) -> None:
        self.service._grab_frame = AsyncMock(
            side_effect=[
                (1.0, "frame-one"),
                (2.0, None),
                (3.0, "frame-three"),
                (4.0, None),
            ]
        )
        self.service._describe_frame = AsyncMock(
            side_effect=[
                (1.0, "desc one"),
                (3.0, "desc three"),
            ]
        )

        result = asyncio.run(
            self.service.extract_and_describe_keyframes(
                video_url="https://cdn.example/video.mp4",
                duration=60,
                title="Example",
                categories=["cat1"],
                tags=["tag1"],
            )
        )

        self.assertEqual(
            [(item.timestamp, item.description) for item in result],
            [(1.0, "desc one"), (3.0, "desc three")],
        )
