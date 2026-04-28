from src.resources.ingest import IngestResource
from src.resources.repository import ResourceRepository


class ResourceService:
    def __init__(
        self,
        *,
        ingest: IngestResource,
        repo: ResourceRepository,
    ):
        self.ingest = ingest
        self.repo = repo
        
        
    async def ingest_resource(self, url: str) -> None:
        return await self.ingest.extract(url=url)