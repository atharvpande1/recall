from src.exceptions import AppError


class UnsupportedResourceUrlError(AppError):
    def __init__(self, *, platform: str, url: str):
        super().__init__(
            status_code=422,
            detail=[
                {
                    "type": "unsupported_resource_url",
                    "loc": ["query", "resource_url"],
                    "msg": f"{platform} URLs are not supported yet",
                    "input": url,
                }
            ],
        )