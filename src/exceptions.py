from dataclasses import dataclass
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


@dataclass(slots=True)
class AppError(Exception):
    status_code: int
    detail: Any


class InvalidResourceUrlError(AppError):
    @classmethod
    def from_validation_errors(cls, *, url: str, errors: list[dict[str, Any]]) -> "InvalidResourceUrlError":
        detail: list[dict[str, Any]] = []
        for error in errors:
            detail.append(
                {
                    "type": error.get("type"),
                    "loc": ["query", "resource_url"],
                    "msg": error.get("msg"),
                    "input": error.get("input", url),
                }
            )

        return cls(status_code=422, detail=detail)


class ResourceResolutionError(AppError):
    def __init__(self, *, url: str, msg: str = "Unable to resolve destination URL"):
        super().__init__(
            status_code=502,
            detail=[
                {
                    "type": "resource_resolution_failed",
                    "loc": ["query", "resource_url"],
                    "msg": msg,
                    "input": url,
                }
            ],
        )


class MissingHttpClientError(AppError):
    def __init__(self):
        super().__init__(
            status_code=500,
            detail=[
                {
                    "type": "http_client_unavailable",
                    "loc": ["server", "http_client"],
                    "msg": "Shared HTTP client is not available in request state",
                    "input": None,
                }
            ],
        )


class MissingBrowserError(AppError):
    def __init__(self):
        super().__init__(
            status_code=500,
            detail=[
                {
                    "type": "browser_unavailable",
                    "loc": ["server", "browser"],
                    "msg": "Shared Playwright browser is not available in request state",
                    "input": None,
                }
            ],
        )


def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})