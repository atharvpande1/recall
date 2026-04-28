from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from dataclasses import dataclass, field


class Platform(StrEnum):
    YOUTUBE = "youtube"
    REDDIT = "reddit"
    WEB = "web"
    

class ResourceType(StrEnum):
    VIDEO: str = "video"
    SHORT: str = "short"
    PLAYLIST: str = "playlist"
    CHANNEL: str = "channel"
    REDDIT_POST: str = "reddit_post"
    ARTICLE: str = "article"
    
    # INSTAGRAM = "instagram"
    # TWITTER = "twitter"
    
    
class YoutubeUrlType(StrEnum):
    SHORT = "short"
    VIDEO = "video"
    CHANNEL = "channel"
    PLAYLIST = "playlist"
    UNKNOWN = "unknown"


class RedditUrlType(StrEnum):
    POST = "post"
    SUBREDDIT = "subreddit"
    USER_PROFILE = "user_profile"
    UNKNOWN = "unknown"
    
    
class RedditPostType(StrEnum):
    TEXT_ONLY = "text_only"
    IMAGE = "image"
    VIDEO = "video"
    EXTERNAL = "external"
    GALLERY = "gallery"
    YOUTUBE = "youtube"
    UNSUPPORTED = "unsupported"
    
    
    
@dataclass
class TranscriptSegment:
    start: float
    duration: float
    text: str
    

@dataclass
class VideoTranscript:
    id: str
    segments: list[TranscriptSegment]
    full_text: str
    language: str | None
    category: str | list[str]


@dataclass
class YoutubeVideoMetadata:
    id: str | None
    url: str | None
    title: str | None
    description: str | None
    thumbnail: str | None
    type: YoutubeUrlType
    uploader: str | None
    uploader_id: str | None
    channel_url: str | None
    upload_date: str | None
    modified_date: str | None
    worst_quality_url: str | None
    duration: int | None
    language: str | None
    categories: list[str] | None
    tags: list[str] | None
    chapters: list[dict] | None
    view_count: int | None
    like_count: int | None
    comment_count: int | None
    is_short: bool
    age_restricted: bool
    is_live: bool
    
    
@dataclass
class KeyframeDescription:
    timestamp: float
    description: str
    
    
@dataclass
class YoutubePlaylistMetadata:
    id: str | None
    url: str | None
    title: str | None
    description: str | None
    modified_date: datetime | None
    tags: list[str] | None
    thumbnail_url: str | None
    video_count: int | None
    channel_id: str | None
    channel_name: str | None
    channel_url: str | None
    uploader_id: str | None
    uploader_name: str | None
    uploader_url: str | None
    entries: list[YoutubeVideoMetadata] | None = None
    yt_type: YoutubeUrlType = YoutubeUrlType.PLAYLIST


@dataclass
class YoutubeChannelMetadata:
    id: str | None
    channel_name: str | None
    uploader_name: str | None
    uploader_id: str | None
    channel_url: str | None
    uploader_url: str | None
    title: str | None
    subscriber_count: int | None
    description: str | None
    thubmnail_url: str | None


@dataclass
class YoutubeVideoScrapeResult:
    metadata: YoutubeVideoMetadata
    transcript: VideoTranscript | None
    keyframes: list[KeyframeDescription] = field(default_factory=list)
    metadata_only: bool = False
    resource_type: ResourceType = ResourceType.VIDEO
    
    
@dataclass
class YoutubePlaylistScrapeResult:
    metadata: YoutubePlaylistMetadata
    videos: list[YoutubeVideoScrapeResult] = field(default_factory=list)
    resource_type: ResourceType = ResourceType.PLAYLIST
    
    
@dataclass
class YoutubeChannelScrapeResult:
    metadata: YoutubeChannelMetadata
    resource_type: ResourceType = ResourceType.CHANNEL
    

@dataclass
class ArticleMetadata:
    title: str | None
    license: str | None
    language: str | None
    tags: str | None
    author: str | None
    date: str | None
    pagetype: str | None
    categories: str | None
    source_hostname: str | None
    hostname: str | None

    
@dataclass
class ArticleScrapeResult:
    text: str
    url: str
    image: str | None
    metadata: ArticleMetadata
    
    
@dataclass
class ScrapeResult:
    data: YoutubeVideoScrapeResult | YoutubePlaylistScrapeResult | YoutubeChannelScrapeResult | ArticleScrapeResult | RedditPostScrapeResult
    platform: Platform
    resource_type: ResourceType


# Reddit dataclasses

@dataclass
class RedditPostScrapeResult:
    id: str | None
    title: str | None
    text: str | None
    url: str | None
    subreddit_name_prefixed: str | None
    num_comments: int | None
    top_comments: list[dict] = field(default_factory=list)
    post_type: RedditPostType | None = None
    media_url: str | None = None
    duration: int | None = None
    keyframes: list[KeyframeDescription] = field(default_factory=list)
    resource_type: ResourceType = ResourceType.REDDIT_POST
