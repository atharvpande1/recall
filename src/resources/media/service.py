import asyncio
import base64

from google.genai import types as genai_types

from src.resources.types import KeyframeDescription
from src.resources.utils import get_frame_timestamps_for_duration


_ffmpeg_sem = asyncio.Semaphore(5)

FRAME_DESCRIPTION_PROMPT = (
    "Describe what is visible in this video frame in 1-2 sentences. "
    "Focus on people, objects, text on screen, and setting. "
    "Be factual and concise. No interpretation."
)
MODEL = "gemini-2.5-flash-lite"


class MediaEnrichmentService:
    def __init__(self, gemini_client):
        self.gemini_client = gemini_client

    async def _grab_frame(
        self,
        video_url: str,
        timestamp: float,
    ) -> tuple[float, str | None]:
        async with _ffmpeg_sem:
            cmd = [
                "ffmpeg",
                "-ss", f"{timestamp:.3f}",
                "-i", video_url,
                "-vframes", "1",
                "-vf", "scale=512:-1",
                "-f", "image2pipe",
                "-vcodec", "mjpeg",
                "pipe:1",
                "-hide_banner", "-loglevel", "error",
            ]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15.0)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                return timestamp, None

            if proc.returncode != 0 or not stdout:
                return timestamp, None

            return timestamp, base64.b64encode(stdout).decode()

    async def _describe_frame(
        self,
        timestamp: float,
        frame_b64: str,
        *,
        title: str | None = None,
        categories: str | None = None,
        tags: str | None = None,
    ) -> tuple[float, str | None]:
        try:
            frame_bytes = base64.b64decode(frame_b64)
            context = []
            if title:
                context.append(f"This frame is from a video titled: {title}.")
            if categories:
                context.append(f"Video categories: {categories}.")
            if tags:
                context.append(f"Video tags: {tags}.")

            prompt = " ".join([*context, FRAME_DESCRIPTION_PROMPT]).strip()

            response = await self.gemini_client.aio.models.generate_content(
                model=MODEL,
                contents=[
                    genai_types.Part.from_bytes(
                        data=frame_bytes,
                        mime_type="image/jpeg",
                    ),
                    prompt,
                ],
            )

            text = getattr(response, "text", None)
            return timestamp, text.strip() if text else None
        except Exception:
            return timestamp, None

    async def extract_and_describe_keyframes(
        self,
        video_url: str,
        duration: int,
        *,
        title: str | None = None,
        categories: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> list[KeyframeDescription]:
        if not video_url or not duration:
            return []

        timestamps = get_frame_timestamps_for_duration(duration)
        frames = await asyncio.gather(*[
            self._grab_frame(video_url, ts)
            for ts in timestamps
        ])

        valid_frames = [(ts, frame_b64) for ts, frame_b64 in frames if frame_b64 is not None]
        if not valid_frames:
            return []

        descriptions = await asyncio.gather(*[
            self._describe_frame(
                ts,
                frame_b64,
                title=title,
                categories=", ".join(categories) if categories else None,
                tags=", ".join(tags) if tags else None,
            )
            for ts, frame_b64 in valid_frames
        ])

        return [
            KeyframeDescription(timestamp=ts, description=description)
            for ts, description in descriptions
            if description
        ]
