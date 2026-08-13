"""Site inspection: detect the generator/framework and discover the resources
that tell us how to turn the site into a book (sitemap, search index, source
repo, table of contents).

Every site is different; this module is the router that picks a strategy.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests

DEFAULT_TIMEOUT = 30
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0 Safari/537.36"
)

GENERATOR_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("bookdown", re.compile(r"bookdown", re.I)),
    ("docusaurus", re.compile(r"docusaurus", re.I)),
    ("mkdocs", re.compile(r"mkdocs", re.I)),
    ("hugo", re.compile(r"hugo", re.I)),
    ("gitbook", re.compile(r"gitbook", re.I)),
    ("sphinx", re.compile(r"sphinx|readthedocs", re.I)),
    ("vuepress", re.compile(r"vuepress", re.I)),
    ("vitepress", re.compile(r"vitepress", re.I)),
    ("hexo", re.compile(r"hexo", re.I)),
    ("jekyll", re.compile(r"jekyll", re.I)),
    ("gatsby", re.compile(r"gatsby", re.I)),
    ("nextjs", re.compile(r"__next|next\.js", re.I)),
]

# Static sites are usually fine with plain requests; these markers suggest the
# content is rendered by JavaScript and needs a browser (crawl4ai/playwright).
DYNAMIC_HINTS = [
    re.compile(r'<div\s+id=["\'](root|app|__next|__nuxt)["\']', re.I),
    re.compile(r'<script[^>]+src=["\'][^"\']*(main|app|bundle)[^"\']*\.js', re.I),
    re.compile(r"window\.__NUXT__|window\.__NEXT_DATA__|window\.__INITIAL_STATE__", re.I),
]

_HTML_ATTR = r'[^>]*'
_META_NAME = re.compile(
    rf'<meta{_HTML_ATTR}name=[\"\'](?P<name>[^\"\']+)[\"\']{_HTML_ATTR}content=[\"\'](?P<content>[^\"\']*)[\"\']',
    re.I,
)
_META_PROPERTY = re.compile(
    rf'<meta{_HTML_ATTR}property=[\"\']og:title[\"\']{_HTML_ATTR}content=[\"\'](?P<content>[^\"\']*)[\"\']',
    re.I,
)


def _meta_tags(html: str) -> dict[str, str]:
    tags: dict[str, str] = {}
    for m in _META_NAME.finditer(html):
        tags.setdefault(m.group("name").strip().lower(), m.group("content").strip())
    return tags


def detect_generator(html: str) -> Optional[str]:
    """Best-effort generator detection from <meta name="generator"> or HTML
    fingerprints. Returns the raw meta value when present, else a matched
    framework name, else None."""
    tags = _meta_tags(html)
    gen = tags.get("generator")
    if gen:
        return gen
    for name, pat in GENERATOR_PATTERNS:
        if pat.search(html):
            return name
    return None


def find_github_repo(html: str) -> Optional[str]:
    """bookdown and friends often publish <meta name="github-repo"> pointing at
    the source repository — the cleanest possible 'book' (Rmd/MD sources)."""
    tags = _meta_tags(html)
    repo = tags.get("github-repo")
    if repo and repo.count("/") >= 1:
        return repo
    return None


def find_page_title(html: str) -> Optional[str]:
    m = re.search(r"<title[^>]*>(?P<title>[^<]+)</title>", html, re.I | re.S)
    if m:
        return m.group("title").strip()
    m = _META_PROPERTY.search(html)
    if m:
        return m.group("content").strip()
    return None


def looks_dynamic(html: str) -> bool:
    """True when the page is likely rendered client-side: little visible text
    but script shells (root/app divs, bundles)."""
    text = re.sub(r"<script.*?</script>", "", html, flags=re.I | re.S)
    text = re.sub(r"<style.*?</style>", "", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    words = len(text.split())
    if words >= 50:
        return False
    return any(hint.search(html) for hint in DYNAMIC_HINTS)


@dataclass
class SiteReport:
    url: str
    generator: Optional[str] = None
    title: Optional[str] = None
    github_repo: Optional[str] = None
    sitemap_url: Optional[str] = None
    robots_url: Optional[str] = None
    search_index_url: Optional[str] = None
    dynamic: bool = False
    toc_link_count: int = 0
    page_count_estimate: int = 0
    strategy: str = "unknown"
    strategy_reason: str = ""
    notes: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(self.__dict__, ensure_ascii=False, indent=2)


def _same_host(base: str, candidate: str) -> bool:
    return urlparse(urljoin(base, candidate)).netloc == urlparse(base).netloc


def _base_dir(url: str) -> str:
    """Directory of a URL path, e.g. https://host/a/b/page.html → https://host/a/b/"""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    if "." in path.split("/")[-1]:
        path = path.rsplit("/", 1)[0]
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def _first_ok(session: requests.Session, urls: list[str]) -> Optional[str]:
    for u in urls:
        try:
            resp = session.get(u, timeout=DEFAULT_TIMEOUT)
            if resp.status_code == 200 and resp.text:
                return resp.url
        except requests.RequestException:
            continue
    return None


def discover_resources(base_url: str, html: str, session: requests.Session) -> tuple[Optional[str], Optional[str], Optional[str], bool]:
    """Probe the conventional resource endpoints, base path first, then origin
    root (sites often live under a sub-path such as /rmarkdown-book/).

    Returns (sitemap_url, robots_url, search_index_url, dynamic)."""
    base = _base_dir(base_url)
    parsed = urlparse(base_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    sitemap_url: Optional[str] = None
    robots_url: Optional[str] = None
    search_index_url: Optional[str] = None

    # robots.txt first — it may declare the sitemap location.
    robots_url = _first_ok(session, [f"{base}/robots.txt", f"{origin}/robots.txt"])
    if robots_url:
        try:
            robots = session.get(robots_url, timeout=DEFAULT_TIMEOUT).text
            for line in robots.splitlines():
                lm = re.match(r"(?i)\s*Sitemap:\s*(\S+)", line)
                if lm:
                    sitemap_url = lm.group(1)
        except requests.RequestException:
            pass

    if sitemap_url is None:
        sitemap_url = _first_ok(
            session,
            [
                f"{base}/sitemap.xml",
                f"{origin}/sitemap.xml",
                f"{origin}/sitemap_index.xml",
            ],
        )

    # bookdown ships a built-in search index that carries the full text.
    search_url = _first_ok(
        session, [f"{base}/search_index.json", f"{origin}/search_index.json"]
    )
    if search_url:
        try:
            payload = json.loads(session.get(search_url, timeout=DEFAULT_TIMEOUT).text)
            if isinstance(payload, list) and payload and isinstance(payload[0], list):
                search_index_url = search_url
        except (json.JSONDecodeError, IndexError, requests.RequestException):
            pass

    return sitemap_url, robots_url, search_index_url, looks_dynamic(html)


def count_toc_links(html: str, base_url: str) -> int:
    """Count same-host .html links in the first page — a rough proxy for 'is
    this a book-like site with a navigable table of contents'."""
    seen: set[str] = set()
    for m in re.finditer(r'href=["\'](?P<href>[^"\']+)["\']', html, re.I):
        href = m.group("href")
        full = urljoin(base_url, href)
        if _same_host(base_url, full) and re.search(r"\.html?(?:$|[#?])", href, re.I):
            seen.add(full.split("#")[0])
    return len(seen)


def recommend_strategy(report: SiteReport) -> None:
    """Pick the best book-extraction strategy based on what was discovered."""
    if report.github_repo:
        report.strategy = "source-repo"
        report.strategy_reason = (
            f'<meta name="github-repo" content="{report.github_repo}">: the book '
            "source is public — fetch the Rmd/MD files instead of scraping HTML"
        )
    elif report.search_index_url:
        report.strategy = "search-index"
        report.strategy_reason = (
            "bookdown search_index.json carries per-page full text — no crawling needed"
        )
    elif report.sitemap_url:
        report.strategy = "sitemap"
        report.strategy_reason = f"sitemap at {report.sitemap_url}"
    elif report.toc_link_count >= 5:
        report.strategy = "toc"
        report.strategy_reason = (
            f"{report.toc_link_count} same-host .html links found on the landing page"
        )
    else:
        report.strategy = "bfs"
        report.strategy_reason = "no sitemap/search-index/ToC — fall back to bounded BFS crawl"


def inspect_site(url: str, session: Optional[requests.Session] = None) -> SiteReport:
    """Fetch the landing page and produce a SiteReport with a recommended
    strategy. This is what the site_inspect tool calls."""
    close = session is None
    session = session or requests.Session()
    session.headers.setdefault("User-Agent", USER_AGENT)
    report = SiteReport(url=url)
    try:
        resp = session.get(url, timeout=DEFAULT_TIMEOUT)
        if resp.status_code != 200 or not resp.text:
            report.notes.append(f"GET {url} → HTTP {resp.status_code}")
            return report
        html = resp.text
        report.url = resp.url
        report.generator = detect_generator(html)
        report.title = find_page_title(html)
        report.github_repo = find_github_repo(html)
        report.dynamic = looks_dynamic(html)
        (
            report.sitemap_url,
            report.robots_url,
            report.search_index_url,
            _,
        ) = discover_resources(report.url, html, session)
        report.toc_link_count = count_toc_links(html, report.url)
        if report.github_repo:
            # estimate chapter count from the source repo listing (cheap, and
            # avoids guessing from HTML when we can just list files)
            try:
                api = f"https://api.github.com/repos/{report.github_repo}/contents/"
                r = session.get(api, timeout=DEFAULT_TIMEOUT)
                if r.status_code == 200:
                    items = json.loads(r.text)
                    if isinstance(items, list):
                        report.page_count_estimate = len(items)
            except (requests.RequestException, json.JSONDecodeError):
                pass
        if report.search_index_url:
            try:
                r = session.get(report.search_index_url, timeout=DEFAULT_TIMEOUT)
                payload = json.loads(r.text)
                if isinstance(payload, list):
                    report.page_count_estimate = len(payload)
            except (requests.RequestException, json.JSONDecodeError):
                pass
        if report.page_count_estimate == 0:
            report.page_count_estimate = max(report.toc_link_count, 1)
        recommend_strategy(report)
    except requests.RequestException as exc:
        report.notes.append(f"request failed: {exc}")
    finally:
        if close:
            session.close()
    return report
