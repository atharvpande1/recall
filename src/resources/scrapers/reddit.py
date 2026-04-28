import httpx
import re

from src.resources.media import MediaEnrichmentService
from src.resources.scrapers.base import BaseScraper, ScrapeResult
from src.resources.types import (
    Platform,
    RedditUrlType,
    RedditPostScrapeResult,
    RedditPostType,
)


_REDDIT_POST_RE = re.compile(
    r"^/r/[^/]+/comments/[^/]+(?:/.*)?/?$",
    flags=re.IGNORECASE,
)
_REDDIT_SUBREDDIT_RE = re.compile(
    r"^/r/[^/]+/?$",
    flags=re.IGNORECASE,
)
_REDDIT_USER_PROFILE_RE = re.compile(
    r"^/(?:u|user)/[^/]+/?$",
    flags=re.IGNORECASE,
)


class RedditScraper(BaseScraper):
    def __init__(
        self,
        client: httpx.AsyncClient,
        media_service: MediaEnrichmentService | None = None,
    ):
        super().__init__(client=client)
        self.media_service = media_service
    
    
    async def fetch_json(self, url: str) -> dict:
        try:
            response = await self.client.get(
                self._check_json_suffix(url),
                headers={
                    "User-Agent": "python:com.recall.app:v1.0.0 (by /u/Uber_madlad19)"
                }
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError:
            return None
        
        
    def _check_json_suffix(self, url: str) -> str:
        if not url.endswith(".json"):
            return url + ".json"
        return url
    
    
    def _classify_post(self, post: dict) -> RedditPostType:
        post_hint = post.get('post_hint')
        selftext = post.get('selftext')
        is_gallery = post.get('is_gallery', False)
        domain = post.get('domain') or ""
        url = post.get('url') or ""
        has_text = bool(selftext) and selftext not in ("[removed]", "[deleted]")
        
        
        if is_gallery:
            return RedditPostType.GALLERY

        # youtube
        if any(yt in domain for yt in ("youtube.com", "youtu.be")):
            return RedditPostType.YOUTUBE

        # reddit-hosted video — may also have selftext, handled in scraper
        if post_hint == "hosted:video" or domain == "v.redd.it":
            return RedditPostType.VIDEO

        # rich embed (Twitch etc)
        if post_hint == "rich:video":
            return RedditPostType.EXTERNAL

        # direct image — may also have selftext, handled in scraper
        if post_hint == "image" or domain in ("i.redd.it", "i.imgur.com"):
            return RedditPostType.IMAGE

        # external link — may also have selftext as context
        if post_hint == "link" or (url and not url.startswith("https://www.reddit.com")):
            return RedditPostType.EXTERNAL

        # pure text — no media at all
        if has_text:
            return RedditPostType.TEXT_ONLY

        return RedditPostType.UNSUPPORTED
    

    def _get_post_type(self, post: dict) -> RedditPostType:
        return self._classify_post(post)
    
    
    def _parse_post_response(self, response: list[dict]) -> tuple[dict, list[dict]]:
        post =  response[0].get('data', {}).get('children', [{}])[0].get('data', {})
        comments = response[1].get('data', {}).get('children', [{}])

        def _is_natural_comment(comment: dict) -> bool:
            if comment.get("kind") != "t1":
                return False

            data = comment.get("data", {})
            author = (data.get("author") or "").strip().lower()
            body = (data.get("body") or "").strip().lower()
            distinguished = (data.get("distinguished") or "").strip().lower()

            if not author or author in {"[deleted]", "[removed]"}:
                return False

            if author == "automoderator" or "bot" in author:
                return False

            if distinguished in {"moderator", "admin"}:
                return False

            if body in {"[deleted]", "[removed]"}:
                return False

            return True

        top_comments = [
            c.get("data", {})
            for c in comments
            if _is_natural_comment(c)
        ][:3]
        
        return post, top_comments
    
    
    def _scrape_text_post(self, post: dict, url: str) -> RedditPostScrapeResult:
        return RedditPostScrapeResult(
            id=post.get('name'),
            title=post.get('title'),
            text=post.get('selftext'),
            url=f"https://www.reddit.com{post.get('permalink')}" if post.get('permalink') else url,
            subreddit_name_prefixed=post.get('subreddit_name_prefixed'),
            num_comments=post.get('num_comments'),
        )
        

    def _extract_video_media(self, post: dict) -> tuple[str | None, int | None]:
        reddit_video = (
            (post.get("media") or {}).get("reddit_video")
            or (post.get("secure_media") or {}).get("reddit_video")
            or (post.get("preview") or {}).get("reddit_video_preview")
            or {}
        )
        return reddit_video.get("fallback_url"), reddit_video.get("duration")
    
    
    async def scrape_post(self, url: str):
        response = await self.fetch_json(url)
        post, top_comments = self._parse_post_response(response)
        
        post_type = self._get_post_type(post)
        
        match post_type:
            case RedditPostType.TEXT_ONLY:
                result = self._scrape_text_post(post, url)
                result.top_comments = top_comments
                result.post_type = post_type
                return result
            case RedditPostType.VIDEO:
                media_url, duration = self._extract_video_media(post)
                keyframes = []
                if (
                    self.media_service is not None
                    and media_url
                    and duration
                    and duration <= 300
                ):
                    keyframes = await self.media_service.extract_and_describe_keyframes(
                        media_url,
                        duration,
                        title=post.get("title"),
                    )
                return RedditPostScrapeResult(
                    id=post.get('name'),
                    title=post.get('title'),
                    text=post.get('selftext'),
                    url=f"https://www.reddit.com{post.get('permalink')}" if post.get('permalink') else url,
                    subreddit_name_prefixed=post.get('subreddit_name_prefixed'),
                    num_comments=post.get('num_comments'),
                    top_comments=top_comments,
                    post_type=post_type,
                    media_url=media_url,
                    duration=duration,
                    keyframes=keyframes,
                )

        return RedditPostScrapeResult(
            id=post.get('name'),
            title=post.get('title'),
            text=post.get('selftext'),
            url=f"https://www.reddit.com{post.get('permalink')}" if post.get('permalink') else url,
            subreddit_name_prefixed=post.get('subreddit_name_prefixed'),
            num_comments=post.get('num_comments'),
            top_comments=top_comments,
            post_type=post_type,
        )
        
    
    
    def _detect_url_type(self, url: str) -> RedditUrlType:
        try:
            from urllib.parse import urlparse

            path = urlparse(url).path
        except Exception:
            return RedditUrlType.UNKNOWN

        if _REDDIT_POST_RE.match(path):
            return RedditUrlType.POST

        if _REDDIT_SUBREDDIT_RE.match(path):
            return RedditUrlType.SUBREDDIT

        if _REDDIT_USER_PROFILE_RE.match(path):
            return RedditUrlType.USER_PROFILE

        return RedditUrlType.UNKNOWN
    
    
    async def scrape(
        self,
        url: str,
        *,
        fragment: str | None = None,
        tracking_query_params: dict[str, list[str]] | None = None,
    ) -> ScrapeResult:
        
        reddit_url_type = self._detect_url_type(url)
        
        match reddit_url_type:
            case RedditUrlType.POST:
                data = await self.scrape_post(url)
            case _:
                raise NotImplementedError(f"Unsupported reddit URL type: {reddit_url_type}")

        return ScrapeResult(
            platform=Platform.REDDIT,
            data=data,
            resource_type=data.resource_type,
        )
