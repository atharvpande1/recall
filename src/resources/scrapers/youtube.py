import asyncio
from datetime import datetime

import httpx
import yt_dlp
from fastapi import status

from src.resources.media import MediaEnrichmentService
from src.resources.scrapers.base import BaseScraper, ScrapeResult

from src.resources.types import (
    Platform,
    YoutubeUrlType,
    YoutubeChannelMetadata,
    YoutubePlaylistMetadata,
    YoutubeVideoMetadata,
    VideoTranscript,
    TranscriptSegment,
    KeyframeDescription,
    YoutubeVideoScrapeResult,
    YoutubePlaylistScrapeResult,
    YoutubeChannelScrapeResult
)
from src.resources.utils import (
    classify_youtube_url,
    get_frame_timestamps_for_duration,
    language_base_code,
    normalize_language_code,
    normalize_text,
)
from src.resources.config import resources_settings

class YoutubeScraper(BaseScraper):
    def __init__(
        self,
        client: httpx.AsyncClient,
        media_service: MediaEnrichmentService | None = None,
    ):
        super().__init__(client=client)
        self.media_service = media_service
        
    
    def _get_yt_dlp_config_by_yt_type(
        self,
        yt_type: YoutubeUrlType,
    ) -> dict | None:
        base_opts = {
            "quiet": True,
            "skip_download": True,
            "socket_timeout": 30,
            "retries": 3,
            "geo_bypass": True,
        }
        video_opts = {
            **base_opts,
            "noplaylist": True,
        }
        playlist_opts = {
            **base_opts,
            "extract_flat": "in_playlist",
            "playlistend": 10,
            "ignoreerrors": True,
            "sleep_interval": 1,
            "max_sleep_interval": 3,
        }
        channel_opts = {
            **base_opts,
            "extract_flat": True,
            "playlistend": 0,
            "ignoreerrors": True,
        }

        return {
            YoutubeUrlType.SHORT: video_opts,
            YoutubeUrlType.VIDEO: video_opts,
            YoutubeUrlType.CHANNEL: channel_opts,
            YoutubeUrlType.PLAYLIST: playlist_opts,
            YoutubeUrlType.UNKNOWN: None,
        }.get(yt_type)
        
        
    def _detect_yt_type(self, url: str) -> YoutubeUrlType:
        return classify_youtube_url(url)
        
        
    def _get_worst_quality_url(self, formats: list[dict]) -> str:
        def is_video(f):
            return (
                f.get("vcodec") not in (None, "none")
                and f.get("url")
                and f.get("ext") == "mp4"
            )

        video_formats = [f for f in formats if is_video(f)]
        if not video_formats:
            return None

        # prefer video-only (no mux overhead), fall back to muxed
        video_only = [f for f in video_formats if f.get("acodec") in (None, "none")]
        pool = video_only if video_only else video_formats

        return min(pool, key=lambda f: f.get("height") or 9999)["url"]

    def _str_or_none(self, value: object) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return str(value)

    def _text_or_none(self, value: object) -> str | None:
        if value is None:
            return None
        text = normalize_text(value)
        return text or None

    def _int_or_none(self, value: object) -> int | None:
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _datetime_or_none(self, value: object) -> datetime | None:
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value)
        if isinstance(value, str):
            value = value.strip()
            for fmt in ("%Y%m%d", "%Y%m%d%H%M%S"):
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue
        return None

    def _list_or_none(self, value: object) -> list[str] | None:
        if not value:
            return None
        if not isinstance(value, list):
            return None

        items = []
        for item in value:
            normalized = self._text_or_none(item)
            if normalized is not None:
                items.append(normalized)
        return items or None

    def _build_video_metadata(
        self,
        info: dict,
        *,
        yt_type: YoutubeUrlType,
    ) -> YoutubeVideoMetadata:
        return YoutubeVideoMetadata(
            id=self._str_or_none(info.get("id")),
            url=self._str_or_none(info.get("webpage_url") or info.get("url")),
            title=self._text_or_none(info.get("title")),
            description=self._text_or_none(info.get("description")),
            thumbnail=self._str_or_none(info.get("thumbnail") or info.get("thumbnail_url")),
            type=yt_type,
            uploader=self._text_or_none(info.get("uploader")),
            uploader_id=self._str_or_none(info.get("uploader_id")),
            channel_url=self._str_or_none(info.get("channel_url")),
            upload_date=self._str_or_none(info.get("upload_date")),
            modified_date=self._str_or_none(info.get("modified_date")),
            worst_quality_url=self._str_or_none(self._get_worst_quality_url(info.get("formats") or [])),
            duration=self._int_or_none(info.get("duration")),
            language=self._str_or_none(info.get("language")),
            categories=self._list_or_none(info.get("categories")),
            tags=self._list_or_none(info.get("tags")),
            chapters=info.get("chapters") or None,
            view_count=self._int_or_none(info.get("view_count")),
            like_count=self._int_or_none(info.get("like_count")),
            comment_count=self._int_or_none(info.get("comment_count")),
            is_short="/shorts/" in (info.get("webpage_url") or info.get("url") or ""),
            age_restricted=bool(info.get("age_limit", 0) > 0),
            is_live=bool(info.get("is_live") or info.get("was_live")),
        )

    def _build_playlist_metadata(self, info: dict) -> YoutubePlaylistMetadata:
        raw_entries = info.get("entries") or []
        
        entries = [
            self._build_video_metadata(entry, yt_type=YoutubeUrlType.VIDEO)
            for entry in (info.get("entries") or [])
            if isinstance(entry, dict)
        ] if raw_entries else []

        video_count = self._int_or_none(
            info.get("playlist_count")
            or info.get("n_entries")
            or info.get("entries_count")
        )
        if video_count is None:
            video_count = len(entries)

        return YoutubePlaylistMetadata(
            id=self._str_or_none(info.get("id")),
            url=self._str_or_none(info.get("webpage_url") or info.get("original_url") or info.get("url")),
            title=self._text_or_none(info.get("title")),
            description=self._text_or_none(info.get("description")),
            modified_date=self._datetime_or_none(info.get("modified_date")),
            tags=self._list_or_none(info.get("tags")),
            thumbnail_url=self._str_or_none(info.get("thumbnail") or info.get("thumbnail_url")),
            video_count=video_count,
            channel_id=self._str_or_none(info.get("channel_id")),
            channel_name=self._text_or_none(info.get("channel") or info.get("channel_name")),
            channel_url=self._str_or_none(info.get("channel_url")),
            uploader_id=self._str_or_none(info.get("uploader_id")),
            uploader_name=self._text_or_none(info.get("uploader") or info.get("uploader_name")),
            uploader_url=self._str_or_none(info.get("uploader_url")),
            entries=entries,
        )

    def _build_channel_metadata(self, info: dict) -> YoutubeChannelMetadata:
        return YoutubeChannelMetadata(
            id=self._str_or_none(info.get("id") or info.get("channel_id")),
            channel_name=self._text_or_none(info.get("channel") or info.get("channel_name") or info.get("uploader") or info.get("title")),
            uploader_name=self._text_or_none(info.get("uploader") or info.get("channel") or info.get("title")),
            uploader_id=self._str_or_none(info.get("uploader_id") or info.get("channel_id")),
            channel_url=self._str_or_none(info.get("channel_url")),
            uploader_url=self._str_or_none(info.get("uploader_url") or info.get("channel_url")),
            title=self._text_or_none(info.get("title") or info.get("channel")),
            subscriber_count=self._int_or_none(
                info.get("channel_follower_count")
                or info.get("subscriber_count")
                or info.get("followers")
            ),
            description=self._text_or_none(info.get("description")),
            thubmnail_url=self._str_or_none(info.get("thumbnail") or info.get("thumbnail_url")),
        )
        
        
    def get_yt_metadata(
        self,
        url: str,
        yt_type: YoutubeUrlType | None = None
    ) -> YoutubeVideoMetadata | YoutubePlaylistMetadata | YoutubeChannelMetadata:
        
        if not yt_type:
            yt_type = self._detect_yt_type(url)
        
        with yt_dlp.YoutubeDL(self._get_yt_dlp_config_by_yt_type(yt_type)) as ydl:
            info = ydl.extract_info(url) or {}

            builders = {
                YoutubeUrlType.SHORT: lambda payload: self._build_video_metadata(
                    payload,
                    yt_type=YoutubeUrlType.SHORT,
                ),
                YoutubeUrlType.VIDEO: lambda payload: self._build_video_metadata(
                    payload,
                    yt_type=YoutubeUrlType.VIDEO,
                ),
                YoutubeUrlType.PLAYLIST: self._build_playlist_metadata,
                YoutubeUrlType.CHANNEL: self._build_channel_metadata,
                YoutubeUrlType.UNKNOWN: lambda payload: self._build_video_metadata(
                    payload,
                    yt_type=YoutubeUrlType.UNKNOWN,
                ),
            }

            return builders.get(yt_type, builders[YoutubeUrlType.UNKNOWN])(info)
            

    def _build_video_transcript(
        self,
        *,
        video_id: str | None,
        track: dict | None,
        full_text: str | None,
        category: str | list[str] | None,
        fallback_language: str | None,
    ) -> VideoTranscript | None:
        track = track or {}

        selected_language = (
            normalize_language_code(
                track.get("language")
                or track.get("languageCode")
                or track.get("language_code")
            )
            or normalize_language_code(fallback_language)
        )

        raw_segments = track.get("transcript") or track.get("segments") or []
        if isinstance(raw_segments, dict):
            raw_segments = [raw_segments]
        elif not isinstance(raw_segments, list):
            raw_segments = []

        segments: list[TranscriptSegment] = []
        for seg in raw_segments:
            if not isinstance(seg, dict):
                continue

            text = normalize_text(seg.get("text"))
            if not text:
                continue

            try:
                start = float(seg.get("start"))
            except (TypeError, ValueError):
                start = 0.0

            try:
                duration = float(seg.get("duration"))
            except (TypeError, ValueError):
                duration = 0.0

            segments.append(
                TranscriptSegment(
                    start=start,
                    duration=duration,
                    text=text,
                )
            )

        normalized_full_text = normalize_text(full_text)
        if not normalized_full_text and segments:
            normalized_full_text = " ".join(segment.text for segment in segments)

        if not segments and not normalized_full_text:
            return None

        return VideoTranscript(
            id=video_id,
            segments=segments,
            full_text=normalized_full_text,
            language=selected_language,
            category=category,
        )
        
    
    async def _get_transcipt_by_video_id(
        self, 
        video_ids: list[str],
        preferred_language: str | None = None
    ) -> list[VideoTranscript | None] | None:
        
        MAX_RETRIES = 3
        BASE_RETRY_BACKOFF = 2
        RATE_LIMIT_BACKOFF = 10
        
        attempt = 0
         
        while attempt < MAX_RETRIES:
            try:
                response = await self.client.post(
                    resources_settings.YOUTUBE_TRANSCRIPT_API_URL,
                    headers={
                        "Authorization": f"Basic {resources_settings.YOUTUBE_TRANSCRIPT_API_KEY}"
                    },
                    json={
                        "ids": video_ids
                    }
                )
                
                if response.status_code >= 500:
                    attempt += 1
                    if attempt > MAX_RETRIES:
                        return None
                    await asyncio.sleep(BASE_RETRY_BACKOFF+2*attempt)
                    continue
                
                if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                    retry_after = response.headers.get("Retry-After", RATE_LIMIT_BACKOFF)
                    await asyncio.sleep(int(retry_after))
                    continue
                
                response.raise_for_status()
                data = response.json()
                out: list[VideoTranscript | None] = []

                preferred_lang = normalize_language_code(preferred_language)
                preferred_base = language_base_code(preferred_language)

                for d in data:
                    if not isinstance(d, dict):
                        continue

                    category = (
                        d.get("microformat", {})
                        .get("playerMicroformatRenderer", {})
                        .get("category")
                    )

                    languages = d.get("languages") or []
                    default_lang = next(
                        (
                            normalize_language_code(lang.get("languageCode"))
                            for lang in languages
                            if isinstance(lang, dict) and lang.get("languageCode")
                        ),
                        None,
                    )

                    tracks = d.get("tracks") or []
                    selected_track = None

                    for track in tracks:
                        if not isinstance(track, dict):
                            continue

                        track_lang = normalize_language_code(
                            track.get("language")
                            or track.get("languageCode")
                            or track.get("language_code")
                        )
                        track_base = language_base_code(track_lang)

                        if preferred_lang and track_lang == preferred_lang:
                            selected_track = track
                            break

                        if preferred_base and track_base == preferred_base:
                            selected_track = track
                            break

                    if selected_track is None and tracks:
                        selected_track = next(
                            (track for track in tracks if isinstance(track, dict)),
                            None,
                        )

                    transcript = self._build_video_transcript(
                        video_id=d.get("id"),
                        track=selected_track,
                        full_text=d.get("text"),
                        category=category,
                        fallback_language=default_lang or preferred_lang,
                    )
                    out.append(transcript)

                return out
                    
            except httpx.TimeoutException as e:
                print(str(e))
                
                attempt += 1
                if attempt > MAX_RETRIES:
                    return None
                await asyncio.sleep(BASE_RETRY_BACKOFF ** attempt)
                        
            except httpx.HTTPStatusError as e:
                print(str(e))
                return None
        
    
    async def scrape_video(
        self,
        url: str
    ) -> dict:
        metadata = self.get_yt_metadata(url, yt_type=YoutubeUrlType.VIDEO)
        duration = metadata.duration

        transcript_task = self._get_transcipt_by_video_id(
            [metadata.id], 
            metadata.language
        )

        if duration is not None and duration <= 300:
            if self.media_service is not None and metadata.worst_quality_url:
                keyframes_descriptions_task = self.media_service.extract_and_describe_keyframes(
                    metadata.worst_quality_url,
                    duration,
                    title=metadata.title,
                    categories=metadata.categories,
                    tags=metadata.tags,
                )
                transcript, keyframes_descriptions = await asyncio.gather(
                    transcript_task,
                    keyframes_descriptions_task,
                )
            else:
                transcript = await transcript_task
                keyframes_descriptions = None
        else:
            transcript = await transcript_task
            keyframes_descriptions = None
            
        transcript = transcript[0]
        
        metadata_only = transcript is None and keyframes_descriptions is None
                    
        return YoutubeVideoScrapeResult(
            metadata=metadata,
            transcript=transcript,
            keyframes=keyframes_descriptions,
            metadata_only=metadata_only,
        )

    
    async def scrape_playlist(
        self,
        url: str
    ) -> YoutubePlaylistScrapeResult:
        playlist_metadata = self.get_yt_metadata(url, yt_type=YoutubeUrlType.PLAYLIST)
        
        entries = getattr(playlist_metadata, "entries", None)
        if not entries:
            return YoutubePlaylistScrapeResult(metadata=playlist_metadata)
        
        delattr(playlist_metadata, "entries")
        
        videos = []
        
        for entry in entries:
            videos.append(await self.scrape_video(entry.url))
            
        return YoutubePlaylistScrapeResult(
            metadata=playlist_metadata,
            videos=videos
        )
        
        
    async def scrape_channel(self, url: str) -> YoutubeChannelScrapeResult:
        return YoutubeChannelScrapeResult(
            metadata=self.get_yt_metadata(
                url,
                yt_type=YoutubeUrlType.CHANNEL
            )
        )
        

    async def scrape(
        self,
        url: str,
        *,
        fragment: str | None = None,
        tracking_query_params: dict[str, list[str]] | None = None,
    ) -> ScrapeResult:
        
        yt_type = self._detect_yt_type(url)
        
        print(f"yt_type: {yt_type}")
        
        match yt_type:
            case YoutubeUrlType.SHORT | YoutubeUrlType.VIDEO:
                data = await self.scrape_video(url)
            case YoutubeUrlType.PLAYLIST:
                data = await self.scrape_playlist(url)
            case YoutubeUrlType.CHANNEL:
                data = await self.scrape_channel(url)
            case _:
                pass
        
        return ScrapeResult(
            platform=Platform.YOUTUBE,
            data=data,
            resource_type=data.resource_type,
        )
