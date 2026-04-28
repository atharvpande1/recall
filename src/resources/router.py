from fastapi import APIRouter

from src.resources.dependencies import GetResourceSvc, NormalizeResourceUrl


router = APIRouter(tags=["resources"])


@router.post("/")
async def ingest_resource(
    resource_svc: GetResourceSvc,
    resource_url: NormalizeResourceUrl,
):
    # url = normalized.get("normalized_url")
    # return {"status": "ok", "url": url, "http_client_type": type(request.state.http_client), "browser_type": type(request.state.browser)}
    url = resource_url.get('normalized_url')
    print(url)
    return await resource_svc.ingest_resource(url)