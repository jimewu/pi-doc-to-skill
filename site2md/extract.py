"""Main-content extraction: strip the boilerplate (nav, header, footer, ads,
comments) and return the article body as Markdown.

Priority: trafilatura (fast, static) → crawl4ai (browser-rendered Markdown) →
bs4 fallback (main/article element, else heuristic pruning).
"""

from __future__ import annotations

import re
from typing import Optional


def extract_markdown_static(html: str) -> Optional[str]:
    """trafilatura first (it knows the web's boilerplate patterns), falling
    back to a bs4 main/article extractor."""
    try:
        import trafilatura

        out = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=True,
            output_format="markdown",
            favor_precision=True,
        )
        if out and out.strip():
            return out.strip()
    except Exception:
        pass
    try:
        return _extract_bs4(html)
    except Exception:
        return None


def _extract_bs4(html: str) -> Optional[str]:
    """Minimal bs4 fallback: prefer <article>/<main>, else the body, pruning
    nav/header/footer/aside/script/style and other noise."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    for el in soup(["script", "style", "nav", "header", "footer", "aside", "form", "iframe"]):
        el.decompose()
    for el in soup.select('[class*="cookie"], [class*="advert"], [class*="social"], [class*="comment"]'):
        el.decompose()
    root = soup.find("article") or soup.find("main") or soup.body or soup
    text = root.get_text("\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() or None


def strip_nav_furniture(markdown: str) -> str:
    """Light post-pass on browser/crawl4ai Markdown: drop common one-line
    furniture (prev/next links, breadcrumbs, page footers) that a crawler
    sometimes keeps. Conservative — only removes clearly separate lines."""
    lines = markdown.splitlines()
    kept: list[str] = []
    for line in lines:
        low = line.strip().lower()
        if re.fullmatch(r"(\[?(previous|next|prev|←|→)\b.*\]?|‹.*›|«.*»|table of contents.*)", low):
            continue
        if low.startswith("![](") and not low:
            continue
        kept.append(line)
    return "\n".join(kept)


def page_to_markdown(html: str, url: str = "") -> str:
    """Convert one HTML page to clean Markdown, choosing the best available
    extractor. Never returns None — empty string means extraction failed."""
    out = extract_markdown_static(html)
    if out:
        return strip_nav_furniture(out)
    # static extraction failed or empty: the page may be JS-rendered
    out = _extract_bs4(html)
    return strip_nav_furniture(out or "")
