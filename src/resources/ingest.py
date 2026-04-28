import httpx
from google import genai
from playwright.async_api import Browser

from src.exceptions import ResourceResolutionError
from src.resources.media import MediaEnrichmentService
from src.resources.scrapers.base import ScrapeResult, BaseScraper
from src.resources.scrapers.reddit import RedditScraper
from src.resources.scrapers.web import WebScraper
from src.resources.scrapers.youtube import YoutubeScraper
from src.resources.types import Platform
from src.resources.utils import get_resource_type


class IngestResource:
    def __init__(
        self,
        http_client: httpx.AsyncClient | None = None,
        browser: Browser | None = None,
        gemini_client: genai.Client | None = None,
        media_service: MediaEnrichmentService | None = None,
    ):
        self.client = http_client
        self.browser = browser
        self.media_service = media_service or (
            MediaEnrichmentService(gemini_client=gemini_client)
            if gemini_client is not None else None
        )
        self.scrapers = {
            Platform.WEB: WebScraper(client=http_client, browser=browser),
            Platform.REDDIT: RedditScraper(client=http_client, media_service=self.media_service),
            Platform.YOUTUBE: YoutubeScraper(client=http_client, media_service=self.media_service),
        }
    
    
    async def _resolve_destination_url(self, url: str) -> str:
        try:
            response = await self.client.head(url)
            if response.status_code in {405, 501}:
                response = await self.client.get(url)
        except httpx.RequestError as exc:
            raise ResourceResolutionError(url=url) from exc
        return str(response.url)
    
    
    def _get_extractor_for_url(
        self,
        final_url: str,
    ) -> BaseScraper:
        resource_type = get_resource_type(final_url)
        return self.scrapers[resource_type]

    
    async def extract(
        self,
        *,
        url: str,
        tracking_query_params: dict[str, list[str]] = None,
        fragment: str = None,
    ) -> ScrapeResult:
        final_url = await self._resolve_destination_url(url)
        scraper = self._get_extractor_for_url(final_url)
        
        return await scraper.scrape(
            final_url,
            fragment=fragment,
            tracking_query_params=tracking_query_params,
        )
