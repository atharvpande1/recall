import json
import re
import trafilatura
import asyncio
import httpx
from pydantic import HttpUrl
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from urllib.parse import urlsplit


medium_url = "https://medium.com/@artur.rakhmatulin/a-little-sqlalchemy-2-0-guide-66090ea2b3f9"
dev_to_url = "https://dev.to/ctrix/python-concurrency-a-guide-to-threads-processes-and-asyncio-45n4"

docs_url = "https://driver-behavior-score.onrender.com/docs#/auth/create_api_key_auth_api_keys_post"

docs_url_without_fragment = "https://www.driver-behavior-score.onrender.com/docs?a=1"

another_medium_url = "https://medium.com/@michalmalewicz/vibe-coding-is-over-5a84da799e0d"

freedium_url = "https://freedium-mirror.cfd/https://medium.com/@michalmalewicz/vibe-coding-is-over-5a84da799e0d"

ndtv_url = "https://www.ndtv.com/india-news/noida-workers-protest-phase-2-vehicles-burnt-stones-thrown-as-noida-workers-protest-for-better-pay-11349392"

substack_url = "https://substack.com/@aaronparnas/note/c-233934688"

toi_url = "https://timesofindia.indiatimes.com/world/us/us-centcom-says-hormuz-blockade-will-begin-monday-and-will-only-apply-to-iranian-ports-china-will-be-most-affected/articleshow/130224373.cms"

another_toi_url = "https://timesofindia.indiatimes.com/city/noida/noida-workers-protest-news-live-noida-traffic-advisory-road-blocks-salary-hike-violent-in-noida-traffic-jam-police-latest-news/liveblog/130229284.cms"

alzahra_url = "https://www.aljazeera.com/economy/2026/4/13/oil-prices-surge-past-103-a-barrel-after-us-announces-blockade-of-iran"

medium_article_1 = "https://medium.com/algomart/designing-a-fastapi-llm-system-for-10k-concurrent-users-and-scaling-rag-to-100k-daily-users-c54be7acd865"

tds_article = "https://towardsdatascience.com/the-art-of-effective-visualization-of-multi-dimensional-data-6c7202990c57/"

# with httpx.Client() as client:
#     response = client.get(dev_to_url)

# paragraphs = justext.justext(response.content, justext.get_stoplist("English"))

# for paragraph in paragraphs:
#     if not paragraph.is_boilerplate:
#         print(paragraph.text)

# print(response.content)

dev_to_url_obj = HttpUrl(docs_url_without_fragment)
# normalized_url = dev_to_url_obj.build(
#     scheme=dev_to_url_obj.scheme,
#     host=dev_to_url_obj.host,
#     path=dev_to_url_obj.path,
# )

# print(dev_to_url_obj.host)


# print(normalized_url.encoded_string())


# with httpx.Client() as client:
#     response = client.get(docs_url)
    
# fragment_response_content = response.content.decode("utf-8")

# with httpx.Client() as client:
#     response = client.get(docs_url_without_fragment)
    
# no_fragment_response_content = response.content.decode("utf-8")

# print(fragment_response_content == no_fragment_response_content)



# with httpx.Client() as client:
#     response = client.get(dev_to_url)
# out = trafilatura.extract(
#     response.text,
#     url=dev_to_url,
#     with_metadata=True,
#     include_tables=True,
#     include_images=False,
#     output_format='json'
# )
    
# json_out = json.loads(out)

# for k,v in json_out.items():
#     print(f"{k}: {v}\n")
# import json
# text_dict = json.loads(text)

def extract_with_trafilatura(text: str, url: str) -> dict:
    raw = trafilatura.extract(
        text,
        url=url,
        with_metadata=True,
        include_tables=True,
        include_images=False,
        include_comments=False,
        include_links=False,
        output_format='json'
    )
    if not raw:
        return {}
    
    try:
        raw_dict = json.loads(raw)
    except json.decoder.JSONDecodeError:
        print(raw)
        return raw
    
    print("Printing raw dict extracted from trafilatura")
    for k,v in raw_dict.items():
        print(f"{k}: {v}\n")
    
    soup = BeautifulSoup(text, "html.parser")
    title = raw_dict.get("title")
    if title in {None, "", "Freedium"} or (isinstance(title, str) and title.endswith(" - Freedium")):
        if soup.h1 and soup.h1.get_text(strip=True):
            title = soup.h1.get_text(" ", strip=True)
        elif soup.title and soup.title.get_text(strip=True):
            title = soup.title.get_text(" ", strip=True).replace(" - Freedium", "")
            

    
    out = {
        'title': title,
        'text': raw_dict.get('raw_text'),
        'image': raw_dict.get('image'),
        'url': raw_dict.get('source'),
        'language': raw_dict.get('language'),
        'license': raw_dict.get('license'),
        'metadata': {
            'tags': raw_dict.get('tags'),
            'author': raw_dict.get('author'),
            'date': raw_dict.get('date'),
            'pagetype': raw_dict.get('pagetype'),
            'categories': raw_dict.get('categories'),
            'source_hostname': raw_dict.get('source-hostname'),
            'hostname': raw_dict.get('hostname'),
        }
    }
    # out = _enrich_with_html_metadata(text, url, out)
    return out


def _enrich_with_html_metadata(html: str, url: str, out: dict) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    metadata = out.setdefault("metadata", {})

    def _meta(*names: str) -> str | None:
        for name in names:
            tag = soup.find("meta", attrs={"name": name}) or soup.find("meta", attrs={"property": name})
            if tag and tag.get("content"):
                value = tag.get("content").strip()
                if value:
                    return value
        return None

    def _coalesce(*values):
        for value in values:
            if value is None:
                continue
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def _csv_normalize(value: str | None) -> str | None:
        if not value:
            return None
        parts = [part.strip() for part in re.split(r"[;,]", value) if part.strip()]
        if not parts:
            return None
        deduped = list(dict.fromkeys(parts))
        return ",".join(deduped)

    # Parse JSON-LD for structured article metadata when available.
    json_ld_objects: list[dict] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = (script.string or script.get_text() or "").strip()
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except Exception:
            continue
        if isinstance(parsed, list):
            json_ld_objects.extend([obj for obj in parsed if isinstance(obj, dict)])
        elif isinstance(parsed, dict):
            if isinstance(parsed.get("@graph"), list):
                json_ld_objects.extend([obj for obj in parsed["@graph"] if isinstance(obj, dict)])
            json_ld_objects.append(parsed)

    article_like = None
    for obj in json_ld_objects:
        type_name = obj.get("@type")
        if isinstance(type_name, list):
            type_names = {str(item).lower() for item in type_name}
        else:
            type_names = {str(type_name).lower()} if type_name else set()
        if {"article", "newsarticle", "blogposting"} & type_names:
            article_like = obj
            break
    if article_like is None and json_ld_objects:
        article_like = json_ld_objects[0]

    json_ld_author = None
    json_ld_date = None
    json_ld_keywords = None
    json_ld_category = None
    json_ld_lang = None
    json_ld_image = None
    json_ld_site = None
    if article_like:
        author_obj = article_like.get("author")
        if isinstance(author_obj, dict):
            json_ld_author = author_obj.get("name")
        elif isinstance(author_obj, list):
            names = [a.get("name") for a in author_obj if isinstance(a, dict) and a.get("name")]
            if names:
                json_ld_author = ", ".join(names)
        elif isinstance(author_obj, str):
            json_ld_author = author_obj

        json_ld_date = _coalesce(article_like.get("datePublished"), article_like.get("dateCreated"))
        json_ld_keywords = article_like.get("keywords")
        json_ld_category = _coalesce(article_like.get("articleSection"), article_like.get("genre"))
        json_ld_lang = article_like.get("inLanguage")

        image_obj = article_like.get("image")
        if isinstance(image_obj, str):
            json_ld_image = image_obj
        elif isinstance(image_obj, dict):
            json_ld_image = image_obj.get("url")
        elif isinstance(image_obj, list):
            for item in image_obj:
                if isinstance(item, str):
                    json_ld_image = item
                    break
                if isinstance(item, dict) and item.get("url"):
                    json_ld_image = item["url"]
                    break

        publisher_obj = article_like.get("publisher")
        if isinstance(publisher_obj, dict):
            json_ld_site = publisher_obj.get("name")

    # Medium/Freedium title pattern: "<title> | by <author> - Freedium"
    author_from_title = None
    page_title_text = soup.title.get_text(" ", strip=True) if soup.title else None
    if page_title_text:
        title_match = re.search(r"\|\s*by\s+(.+?)(?:\s*-\s*Freedium)?$", page_title_text, flags=re.IGNORECASE)
        if title_match:
            author_from_title = title_match.group(1).strip()
    author_from_source_hostname = None
    source_hostname_text = metadata.get("source_hostname")
    if isinstance(source_hostname_text, str):
        source_match = re.search(r"\|\s*by\s+(.+)$", source_hostname_text, flags=re.IGNORECASE)
        if source_match:
            author_from_source_hostname = source_match.group(1).strip()

    host = (urlsplit(url).hostname or "").lower()
    host_no_www = host[4:] if host.startswith("www.") else host

    metadata["author"] = _coalesce(
        metadata.get("author"),
        json_ld_author,
        _meta("author", "article:author", "parsely-author"),
        author_from_source_hostname,
        author_from_title,
    )
    metadata["date"] = _coalesce(
        metadata.get("date"),
        json_ld_date,
        _meta("article:published_time", "og:published_time", "date", "publish-date", "parsely-pub-date"),
    )
    metadata["tags"] = _coalesce(
        _csv_normalize(metadata.get("tags")),
        _csv_normalize(json_ld_keywords if isinstance(json_ld_keywords, str) else ",".join(json_ld_keywords) if isinstance(json_ld_keywords, list) else None),
        _csv_normalize(_meta("keywords", "news_keywords", "parsely-tags", "article:tag")),
    ) or ""
    metadata["categories"] = _coalesce(
        metadata.get("categories"),
        json_ld_category,
        _meta("article:section", "parsely-section"),
        "",
    )
    metadata["source_hostname"] = _coalesce(
        metadata.get("source_hostname"),
        json_ld_site,
        _meta("og:site_name", "application-name"),
        "Medium" if host_no_www.endswith("medium.com") else None,
    )
    metadata["hostname"] = _coalesce(metadata.get("hostname"), host_no_www)

    out["language"] = _coalesce(
        out.get("language"),
        json_ld_lang,
        _meta("og:locale", "language"),
        soup.html.get("lang") if soup.html else None,
    )
    out["image"] = _coalesce(
        out.get("image"),
        json_ld_image,
        _meta("og:image", "twitter:image"),
    )
    out["url"] = _coalesce(out.get("url"), _meta("og:url", "twitter:url"), url)

    return out


def _resolve_fetch_url(url: str) -> str:
    hostname = (urlsplit(url).hostname or "").lower()
    if hostname == "medium.com" or hostname.endswith(".medium.com"):
        return f"https://freedium-mirror.cfd/{url}"
    return url


async def _fetch_with_playwright(url: str) -> str:
    async with async_playwright() as p:
        async def _fetch_once(browser_name: str) -> tuple[int | None, str]:
            print(f'Fetching {url} with {browser_name}')
            browser_launcher = p.chromium if browser_name == "chromium" else p.firefox
            browser = await browser_launcher.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"] if browser_name == "chromium" else None,
            )
            try:
                context = await browser.new_context(
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
                page = await context.new_page()
                await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")

                # Keep CSS/scripts enabled; blocking them can trigger bot defenses.
                await page.route(
                    "**/*",
                    lambda route: route.abort()
                    if route.request.resource_type in ("image", "media", "font")
                    else route.continue_(),
                )

                target_url = url if url.startswith("https://") else url.replace("http://", "https://", 1)
                response = await page.goto(
                    target_url,
                    wait_until="domcontentloaded",
                    timeout=45_000,
                    referer="https://www.google.com/",
                )

                status = response.status if response is not None else None

                try:
                    await page.wait_for_function(
                        "document.body && document.body.innerText.trim().length > 200",
                        timeout=10_000,
                    )
                except Exception:
                    pass

                await _scroll_to_bottom(page)
                return status, await page.content()
            finally:
                await browser.close()

        status, html = await _fetch_once("chromium")
        if status != 403:
            return html

        print(f"Playwright navigation failed for {url}: status {status}. Retrying with Firefox.")
        _, fallback_html = await _fetch_once("firefox")
        return fallback_html

async def _scroll_to_bottom(page) -> None:
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
    
fetch_url = _resolve_fetch_url(tds_article)

# with httpx.Client() as client:
#     response = client.get(fetch_url)
#     html = response.text

html = asyncio.run(_fetch_with_playwright(fetch_url))
# with httpx.Client() as client:
#     response = client.get("https://www.algolia.com/blog/ai/llm-leaderboard")
out = extract_with_trafilatura(html, fetch_url)

print("=======================")

# for k,v in out.items():
#     print(f"{k}: {v}\n")