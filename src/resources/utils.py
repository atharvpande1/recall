import re
from urllib.parse import urlsplit

from src.resources.exceptions import UnsupportedResourceUrlError
from src.resources.types import Platform, YoutubeUrlType


def _hostname_matches(hostname: str, domain: str) -> bool:
    return hostname == domain or hostname.endswith(f".{domain}")


_MEDIUM_FREEDIUM_POST_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?(?:medium\.com|freedium-mirror\.cfd)/(?:@[^/]+/[^/?#]+|p/[^/?#]+|[^/?#]+/[^/?#]+)(?:[/?#]|$)",
    flags=re.IGNORECASE,
)


def is_medium_or_freedium_post_url(url: str) -> bool:
    return bool(_MEDIUM_FREEDIUM_POST_RE.search(url))


def ensure_freedium_prefix(url: str) -> str:
    hostname = (urlsplit(url).hostname or "").lower()
    if hostname == "freedium-mirror.cfd" or hostname.endswith(".freedium-mirror.cfd"):
        return url
    return f"https://freedium-mirror.cfd/{url}"


def get_resource_type(url: str) -> Platform:
    hostname = (urlsplit(url).hostname or "").lower()

    if _hostname_matches(hostname, "reddit.com") or hostname == "redd.it":
        return Platform.REDDIT

    if _hostname_matches(hostname, "youtube.com") or hostname == "youtu.be":
        # raise UnsupportedResourceUrlError(platform="YouTube", url=url)
        return Platform.YOUTUBE

    if _hostname_matches(hostname, "instagram.com"):
        raise UnsupportedResourceUrlError(platform="Instagram", url=url)

    if _hostname_matches(hostname, "x.com") or _hostname_matches(hostname, "twitter.com"):
        raise UnsupportedResourceUrlError(platform="Twitter/X", url=url)

    return Platform.WEB


def classify_youtube_url(yt_url: str) -> YoutubeUrlType:
    try:
        from urllib.parse import urlparse, parse_qs

        parsed = urlparse(yt_url)
        path = parsed.path
        params = parse_qs(parsed.query)
    except Exception:
        return YoutubeUrlType.UNKNOWN

    if not re.search(r"(youtube\.com|youtu\.be)", parsed.netloc):
        return YoutubeUrlType.UNKNOWN

    if "/shorts/" in path:
        return YoutubeUrlType.SHORT

    if "v" in params or "vi" in params or parsed.netloc == "youtu.be":
        return YoutubeUrlType.VIDEO

    if "list" in params:
        return YoutubeUrlType.PLAYLIST

    if re.match(r"^/(@[\w.-]+|c/[\w.-]+|channel/[\w-]+|user/[\w.-]+)(/.*)?$", path):
        return YoutubeUrlType.CHANNEL

    return YoutubeUrlType.UNKNOWN


def normalize_language_code(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().replace("_", "-").lower()
    return normalized or None


def language_base_code(value: str | None) -> str | None:
    normalized = normalize_language_code(value)
    if not normalized:
        return None
    return normalized.split("-", 1)[0]


def normalize_text(value: object) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    return " ".join(value.split())


def get_frame_timestamps_for_duration(duration: int) -> list[float]:
        thresholds = [
            {"threshold": 30,  "n_frames": 3},
            {"threshold": 60,  "n_frames": 4},
            {"threshold": 120, "n_frames": 6},
            {"threshold": 300, "n_frames": 8},
        ]

        n_frames = next(
            (t["n_frames"] for t in thresholds if duration <= t["threshold"]),
            0
        )

        if n_frames == 0:
            return []

        if n_frames == 1:
            return [duration * 0.5]

        start = duration * 0.05
        end = duration * 0.95
        usable = end - start

        return [
            round(start + (usable / (n_frames - 1)) * i, 2)
            for i in range(n_frames)
        ]
