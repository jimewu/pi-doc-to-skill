"""Page retrieval: plain HTTP for static sites, crawl4ai (playwright) for
JavaScript-rendered sites. crawl4ai is a heavy dependency (bundles Chromium),
so it is imported lazily and only used when the static path fails or the
inspection says the page is dynamic."""

from __future__ import annotations

import re
from typing import Optional

import requests

from .inspect import DEFAULT_TIMEOUT, USER_AGENT


def fetch_html(
    url: str,
    session: Optional[requests.Session] = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> Optional[str]:
    """GET the page as raw HTML. Returns None on any failure."""
    close = session is None
    session = session or requests.Session()
    session.headers.setdefault("User-Agent", USER_AGENT)
    try:
        resp = session.get(url, timeout=timeout)
        if resp.status_code == 200 and resp.text:
            return resp.text
        return None
    except requests.RequestException:
        return None
    finally:
        if close:
            session.close()


def has_real_content(html: str, min_words: int = 50) -> bool:
    """Crude check that a static fetch actually got the article text (vs. a
    JS shell or a bot-wall)."""
    text = re.sub(r"<script.*?</script>", "", html, flags=re.I | re.S)
    text = re.sub(r"<style.*?</style>", "", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return len(text.split()) >= min_words


def fetch_markdown_with_browser(url: str, timeout: int = 90) -> Optional[str]:
    """Render the page in a real browser via crawl4ai and return its
    already-cleaned Markdown (crawl4ai strips nav/header/footer by default).

    Imported lazily: crawl4ai + playwright + Chromium are only needed for
    dynamic sites. Returns None if crawl4ai is unavailable or fails.
    """
    try:
        import asyncio

        from crawl4ai import AsyncWebCrawler

        async def _run() -> str:
            async with AsyncWebCrawler() as crawler:
                result = await crawler.arun(
                    url=url,
                    wait_for="domcontentloaded",
                    timeout=timeout * 1000,
                )
                return result.markdown or ""

        return asyncio.run(_run()) or None
    except Exception:
        return None
