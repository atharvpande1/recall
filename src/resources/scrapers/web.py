import json
from urllib.parse import urlparse
import httpx
import trafilatura
from bs4 import BeautifulSoup
from playwright.async_api import Browser

from src.resources.scrapers.base import BaseScraper, ScrapeResult
from src.resources.types import ArticleMetadata, ArticleScrapeResult, Platform, ResourceType
from src.resources.utils import ensure_freedium_prefix, is_medium_or_freedium_post_url


class SharedBrowserContentFetcher:
    def __init__(self, browser: Browser | None = None):
        self.browser = browser
        

    async def fetch_html(self, url: str) -> str | None:
        context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            java_script_enabled=True,
            ignore_https_errors=True,
            locale="en-US",
            viewport={"width": 1366, "height": 768},
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "en-IN,en-US;q=0.9,en;q=0.8",
                "Upgrade-Insecure-Requests": "1",
            },
        )
        try:
            return await self._fetch_from_context(context, url)
        finally:
            await context.close()
            
        
    async def _scroll_to_bottom(self, page) -> None:
        await page.evaluate("""
            async () => {
                await new Promise((resolve) => {
                    let lastHeight = 0;
                    let unchanged = 0;
                    const interval = setInterval(() => {
                        window.scrollTo(0, document.body.scrollHeight);
                        const newHeight = document.body.scrollHeight;
                        if (newHeight === lastHeight) {
                            unchanged++;
                            if (unchanged >= 3) {
                                clearInterval(interval);
                                resolve();
                            }
                        } else {
                            unchanged = 0;
                            lastHeight = newHeight;
                        }
                    }, 300);
                });
            }
        """)    
    

    async def _fetch_from_context(self, context, url: str) -> str | None:
        page = await context.new_page()
        await page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        await page.route(
            "**/*",
            lambda route: route.abort()
            if route.request.resource_type in ("image", "media", "font")
            else route.continue_(),
        )
        await page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=45_000,
            referer="https://www.google.com/",
        )
        try:
            await page.wait_for_function(
                "document.body && document.body.innerText.trim().length > 200",
                timeout=10_000,
            )
        except Exception:
            pass
        
        await self._scroll_to_bottom(page)
        return await page.content()


class WebScraper(BaseScraper):
    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        browser: Browser | None = None,
    ):
        super().__init__(client)
        self.MIN_WORD_COUNT = 50
        self.playwright_fetcher = SharedBrowserContentFetcher(browser=browser)


    async def scrape(
        self,
        url: str,
        *,
        fragment: str | None = None,
        tracking_query_params: dict[str, list[str]] | None = None,
    ) -> ScrapeResult:
        
        fetch_url = self._resolve_fetch_url(url)
        
        html = await self._fetch_html_http(fetch_url)
        result = self._extract_with_trafilatura(html, fetch_url) if html else {}
        
        if self._is_sparse_result(result):
            html = await self.playwright_fetcher.fetch_html(fetch_url)
            result = self._extract_with_trafilatura(html, fetch_url)
            
        if self._is_metadata_sparse(result):
            metadata = self._extract_explicit_metadata(html, fetch_url)
            result['metadata'] = self._merge_metadata(trafilatura_meta=result.get('metadata'), explicit_meta=metadata)

        return ScrapeResult(
            data=ArticleScrapeResult(
                text=result.get("text") or "",
                url=result.get("url") or url,
                image=result.get("image") or None,
                metadata=self._build_article_metadata(result.get("metadata") or {}),
            ),
            platform=Platform.WEB,
            resource_type=ResourceType.ARTICLE,
        )


    async def _scrape_regular_article(self, url: str) -> dict:
        html = await self._fetch_html_http(url)
        result = self._extract_with_trafilatura(html, url) if html else {}
        if self._is_sparse_result(result):
            pw_html = await self.playwright_fetcher.fetch_html(url)
            if pw_html:
                result = self._extract_with_trafilatura(pw_html, url)
        return result
    
    
    def _merge_metadata(
        self, 
        *,
        trafilatura_meta: dict, 
        explicit_meta: dict
    ) -> dict:
        return {
            key: trafilatura_meta.get(key) or explicit_meta.get(key)
            for key in explicit_meta
        }

    def _article_text_or_none(self, value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            value = str(value)
        value = value.strip()
        return value or None

    def _build_article_metadata(self, metadata: dict) -> ArticleMetadata:
        return ArticleMetadata(
            title=self._article_text_or_none(metadata.get("title")),
            license=self._article_text_or_none(metadata.get("license")),
            language=self._article_text_or_none(metadata.get("language")),
            tags=self._article_text_or_none(metadata.get("tags")),
            author=self._article_text_or_none(metadata.get("author")),
            date=self._article_text_or_none(metadata.get("date")),
            pagetype=self._article_text_or_none(metadata.get("pagetype")),
            categories=self._article_text_or_none(metadata.get("categories")),
            source_hostname=self._article_text_or_none(metadata.get("source_hostname")),
            hostname=self._article_text_or_none(metadata.get("hostname")),
        )
    

    async def _scrape_medium_article(self, url: str) -> dict:
        fetch_url = ensure_freedium_prefix(url)

        html = await self._fetch_html_http(fetch_url)
        result = self._extract_with_trafilatura(html, url) if html else {}

        if self._is_sparse_result(result):
            pw_html = await self.playwright_fetcher.fetch_html(fetch_url)
            if pw_html:
                html = pw_html
                result = self._extract_with_trafilatura(html, url)

        explicit_meta = self._extract_explicit_metadata(html or "", url)
        result = self._merge_missing_fields(result, explicit_meta)

        # Medium fallback end-state: keep title+metadata even if text is still sparse.
        if self._is_sparse_result(result):
            return {
                "title": result.get("title"),
                "text": "",
                "image": result.get("image"),
                "url": result.get("url") or url,
                "language": result.get("language"),
                "license": result.get("license"),
                "metadata": result.get("metadata") or {},
            }
        return result
    
    
    def _resolve_fetch_url(self, url: str) -> str:
        if is_medium_or_freedium_post_url(url):
            return ensure_freedium_prefix(url)
        return url
    
    
    def _is_metadata_sparse(self, metadata: dict[str, str]) -> bool:
        return not metadata or not metadata.get("title") or (not metadata.get("date") and not metadata.get("author"))
    

    async def _fetch_html_http(self, url: str) -> str | None:
        if self.client is None:
            return None
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            return response.text
        except httpx.HTTPError:
            return None

    def _extract_with_trafilatura(self, text: str, url: str) -> dict:
        if not text:
            return {}
        raw = trafilatura.extract(
            text,
            url=url,
            with_metadata=True,
            include_tables=True,
            include_images=False,
            include_links=False,
            include_comments=False,
            output_format="json",
        )
        if not raw:
            return {}

        raw_dict = json.loads(raw)
        out = {
            "text": raw_dict.get("raw_text"),
            "image": raw_dict.get("image"),
            "url": raw_dict.get("source"),
            "metadata": {
                "title": raw_dict.get("title"),
                "license": raw_dict.get("license"),
                "language": raw_dict.get("language"),
                "tags": raw_dict.get("tags"),
                "author": raw_dict.get("author"),
                "date": raw_dict.get("date"),
                "pagetype": raw_dict.get("pagetype"),
                "categories": raw_dict.get("categories"),
                "source_hostname": raw_dict.get("source-hostname"),
                "hostname": raw_dict.get("hostname"),
            },
        }
        return out

    def _is_sparse_result(self, result: dict) -> bool:
        if not result:
            return True
        text = (result.get("text") or "").strip()
        title = (result.get("title") or "").strip().lower()
        if len(text.split()) < self.MIN_WORD_COUNT:
            return True
        if title in {"access denied", "error", "apologies, but something went wrong on our end."}:
            return True
        return False
    

    def _extract_explicit_metadata(self, html: str, url: str) -> dict:
        if not html:
            return {}
        soup = BeautifulSoup(html, "html.parser")

        def _meta(*names: str) -> str | None:
            for name in names:
                tag = soup.find("meta", attrs={"name": name}) or soup.find(
                    "meta", attrs={"property": name}
                )
                if tag and tag.get("content"):
                    value = tag.get("content").strip()
                    if value:
                        return value
            return None

        page_title = soup.title.get_text(" ", strip=True) if soup.title else ""

        title = None
        if soup.h1 and soup.h1.get_text(strip=True):
            title = soup.h1.get_text(" ", strip=True)
        else:
            title = (
                _meta("og:title", "twitter:title")
                or (page_title.replace(" - Freedium", "").strip() or None)
            )

        author = _meta("author", "article:author", "parsely-author", "twitter:creator")
        if not author and "| by " in page_title:
            author = page_title.split("| by ", 1)[1].split(" - ", 1)[0].strip()

        tags = _meta("keywords", "news_keywords", "parsely-tags", "article:tag")
        if tags:
            tags = ",".join(part.strip() for part in tags.replace(";", ",").split(",") if part.strip())

        hostname = urlparse(url).hostname

        return {
            "title": title,
            "license": _meta("license"),
            "language": _meta("og:locale", "language") or (soup.html.get("lang") if soup.html else None),
            "tags": tags,
            "author": author,
            "date": _meta(
                "article:published_time",
                "og:published_time",
                "date",
                "publish-date",
                "DC.date.issued",
            ),
            "pagetype": _meta("og:type"),
            "categories": _meta("article:section", "parsely-section"),
            "source_hostname": _meta("og:site_name", "application-name"),
            "hostname": hostname,
        }

    def _merge_missing_fields(self, primary: dict, fallback: dict) -> dict:
        if not primary:
            return fallback
        if not fallback:
            return primary

        merged = dict(primary)
        for key in ("title", "text", "image", "url", "language", "license"):
            if not merged.get(key) and fallback.get(key):
                merged[key] = fallback[key]

        merged_meta = dict(merged.get("metadata") or {})
        fallback_meta = fallback.get("metadata") or {}
        for key, value in fallback_meta.items():
            if not merged_meta.get(key) and value:
                merged_meta[key] = value
        merged["metadata"] = merged_meta
        return merged
