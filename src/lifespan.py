from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

import httpx
from fastapi import FastAPI
from playwright.async_api import async_playwright

from google import genai

from src.config import app_settings



@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=True)
    
    gemini_client = genai.Client(api_key=app_settings.GEMINI_API_KEY)
    
    async with httpx.AsyncClient(
        follow_redirects=True,
        max_redirects=10,
        timeout=httpx.Timeout(10.0, connect=5.0),
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        },
    ) as client:
        try:
            yield {"http_client": client, "browser": browser, "gemini_client": gemini_client}
        finally:
            await browser.close()
            await playwright.stop()
