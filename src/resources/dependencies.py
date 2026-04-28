import re
from dataclasses import dataclass
from typing import Annotated
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

import httpx
from fastapi import Depends, Request
from pydantic import HttpUrl, TypeAdapter, ValidationError
from playwright.async_api import Browser

from google import genai

from src.resources.ingest import IngestResource
from src.resources.repository import ResourceRepository
from src.resources.service import ResourceService

from src.exceptions import InvalidResourceUrlError, MissingBrowserError, MissingHttpClientError


TRACKING_QUERY_KEYS = {
    "dclid",
    "fbclid",
    "gclid",
    "gbraid",
    "igshid",
    "mc_cid",
    "mc_eid",
    "msclkid",
    "ref",
    "ref_src",
    "si",
    "spm",
    "ttclid",
    "twclid",
    "utm_campaign",
    "utm_content",
    "utm_id",
    "utm_medium",
    "utm_source",
    "utm_term",
    "wbraid",
}

URL_ADAPTER = TypeAdapter(HttpUrl)


@dataclass(slots=True)
class ResourceDependencies:
    http_client: httpx.AsyncClient
    browser: Browser
    gemini_client: genai.Client


def _normalize_path(path: str) -> str:
    collapsed_path = re.sub(r"/+", "/", path or "/")
    if not collapsed_path.startswith("/"):
        collapsed_path = f"/{collapsed_path}"
    if collapsed_path != "/" and collapsed_path.endswith("/"):
        collapsed_path = collapsed_path.rstrip("/")
    return quote(collapsed_path, safe="/:@!$&'()*+,;=-._~%")


def normalize_resource_url(resource_url: str) -> dict[str, object]:
    raw_value = resource_url.strip()
    candidate = raw_value if "://" in raw_value else f"https://{raw_value}"
    try:
        validated_url = URL_ADAPTER.validate_python(candidate)
    except ValidationError as exc:
        raise InvalidResourceUrlError.from_validation_errors(url=resource_url, errors=exc.errors()) from exc
    parsed = urlsplit(validated_url.unicode_string())

    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]

    port = parsed.port
    has_non_default_port = port is not None and port not in {80, 443}
    netloc = f"{host}:{port}" if has_non_default_port else host

    tracking_query_params: dict[str, list[str]] = {}
    kept_query_params: list[tuple[str, str]] = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        normalized_key = key.lower()
        if normalized_key in TRACKING_QUERY_KEYS:
            tracking_query_params.setdefault(normalized_key, []).append(value)
            continue
        kept_query_params.append((key, value))

    normalized_url = urlunsplit(
        (
            "https",
            netloc,
            _normalize_path(parsed.path),
            urlencode(kept_query_params, doseq=True),
            "",
        )
    )

    return {
        "normalized_url": normalized_url,
        "tracking_query_params": tracking_query_params,
        "fragment": parsed.fragment or None,
    }


NormalizeResourceUrl = Annotated[dict[str, object], Depends(normalize_resource_url)]


def get_resource_dependencies(request: Request) -> ResourceDependencies:
    http_client = getattr(request.state, "http_client", None)
    if not isinstance(http_client, httpx.AsyncClient):
        raise MissingHttpClientError()
    browser = getattr(request.state, "browser", None)
    if not isinstance(browser, Browser):
        raise MissingBrowserError()
    gemini_client = getattr(request.state, "gemini_client", None)
    if not isinstance(gemini_client, genai.Client):
        raise MissingHttpClientError()
    return ResourceDependencies(
        http_client=http_client,
        browser=browser,
        gemini_client=gemini_client,
    )


def get_http_client(
    request_or_deps: Request | ResourceDependencies,
):
    if isinstance(request_or_deps, ResourceDependencies):
        return request_or_deps.http_client
    http_client = getattr(request_or_deps.state, "http_client", None)
    if not isinstance(http_client, httpx.AsyncClient):
        raise MissingHttpClientError()
    return http_client


def get_browser(
    request_or_deps: Request | ResourceDependencies,
):
    if isinstance(request_or_deps, ResourceDependencies):
        return request_or_deps.browser
    browser = getattr(request_or_deps.state, "browser", None)
    if not isinstance(browser, Browser):
        raise MissingBrowserError()
    return browser


def get_gemini_client(
    request_or_deps: Request | ResourceDependencies,
):
    if isinstance(request_or_deps, ResourceDependencies):
        return request_or_deps.gemini_client
    gemini_client = getattr(request_or_deps.state, "gemini_client", None)
    if not isinstance(gemini_client, genai.Client):
        raise MissingHttpClientError()
    return gemini_client


def get_resource_repo(): # Add db later
    return ResourceRepository()


def get_resource_ingest(
    deps: Annotated[ResourceDependencies, Depends(get_resource_dependencies)],
):
    return IngestResource(
        http_client=deps.http_client,
        browser=deps.browser,
        gemini_client=deps.gemini_client,
    )


def get_resource_svc(
    ingest: Annotated["IngestResource", Depends(get_resource_ingest)],
    repo: Annotated["ResourceRepository", Depends(get_resource_repo)],
):
    return ResourceService(ingest=ingest, repo=repo)

GetResourceSvc = Annotated[ResourceService, Depends(get_resource_svc)]
