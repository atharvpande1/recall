from abc import ABC, abstractmethod
import httpx

from src.resources.types import ScrapeResult


class BaseScraper(ABC):
    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
    ):
        self.client = client
        

    @abstractmethod
    async def scrape(
        self,
        url: str,
        *,
        fragment: str | None = None,
        tracking_query_params: dict[str, list[str]] | None = None,
    ) -> ScrapeResult:
        raise NotImplementedError