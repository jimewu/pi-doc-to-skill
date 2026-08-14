"""site2md CLI — the single entry point behind the pi custom tools.

Usage:
    python3 -m site2md.cli inspect <url>                 # JSON site report
    python3 -m site2md.cli crawl <url> <outdir> [opts]   # build book-like corpus
    python3 -m site2md.cli page-extract <html> <out.md>  # one page → markdown
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import deque
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
import xml.etree.ElementTree as ET

from .assemble import Chapter, write_corpus
from .extract import page_to_markdown, strip_nav_furniture
from .fetch import fetch_html, fetch_markdown_with_browser
from .inspect import DEFAULT_TIMEOUT, USER_AGENT, inspect_site, SiteReport

NOISE_URL_RE = re.compile(
    r"(\.(css|js|png|jpe?g|gif|svg|webp|ico|pdf|zip|gz|tar|woff2?|ttf|eot|mp4|webm|json|xml|txt|rss|atom)$"
    r"|/(tag|tags|category|categories|author|authors|page|login|signup|register|logout|search|api|feed|rss|atom|wp-json|wp-content|assets|static|images?|img|fonts?|css|js)/)"
    r"|[?&](utm_|fbclid|gclid|ref=|replytocom)",
    re.I,
)


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.setdefault("User-Agent", USER_AGENT)
    return s


def _same_host(base: str, candidate: str) -> bool:
    return urlparse(urljoin(base, candidate)).netloc == urlparse(base).netloc


def _normalize(url: str) -> str:
    url = url.split("#")[0]
    if url.endswith("/index.html"):
        url = url[: -len("index.html")]
    return url


def _is_htmlish(url: str) -> bool:
    path = urlparse(url).path.lower()
    if not path or path.endswith("/"):
        return True
    if "." not in path.split("/")[-1]:
        return True
    return path.endswith((".html", ".htm", ".xhtml", ".md", ".rmd", ".qmd"))


def _passes_filters(url: str, include: list[str], exclude: list[str]) -> bool:
    import fnmatch

    if NOISE_URL_RE.search(url):
        return False
    if include and not any(fnmatch.fnmatch(url, pat) for pat in include):
        return False
    if any(fnmatch.fnmatch(url, pat) for pat in exclude):
        return False
    return True


def _guess_title(url: str, markdown: str) -> str:
    for line in markdown.splitlines():
        s = line.strip()
        if s.startswith("# "):
            return s[2:].strip()
    path = urlparse(url).path.rstrip("/").split("/")[-1]
    return path.replace(".html", "").replace("-", " ").replace("_", " ").strip() or url


# ---------------------------------------------------------------------------
# URL-list strategies
# ---------------------------------------------------------------------------

def source_repo_chapters(repo: str, session: requests.Session) -> list[Chapter]:
    """GitHub repo of Rmd/MD sources → chapters straight from the raw files.
    The most comfortable case (bookdown books): no crawling at all."""
    api = f"https://api.github.com/repos/{repo}"
    r = session.get(api, timeout=DEFAULT_TIMEOUT)
    if r.status_code != 200:
        raise RuntimeError(f"GitHub API {r.status_code} for {repo}")
    branch = r.json().get("default_branch", "main")
    tree = session.get(
        f"https://api.github.com/repos/{repo}/git/trees/{branch}?recursive=1",
        timeout=DEFAULT_TIMEOUT,
    )
    if tree.status_code != 200:
        raise RuntimeError(f"cannot list repo tree: HTTP {tree.status_code}")
    items = [
        it
        for it in tree.json().get("tree", [])
        if it.get("type") == "blob"
        and it["path"].lower().endswith((".rmd", ".md", ".qmd", ".markdown"))
        and not it["path"].lower().startswith(("."))
        and it["path"].lower() != "readme.md"
    ]
    # bookdown convention: the book's chapters live in the repo root. Drop
    # sub-directory files (examples/, docs/, ...) unless the root has no
    # chapter files at all (some repos keep chapters/).
    root_items = [it for it in items if "/" not in it["path"]]
    if root_items:
        items = root_items
    items.sort(key=lambda it: it["path"].lower())
    chapters: list[Chapter] = []
    for i, it in enumerate(items, start=1):
        raw_url = f"https://raw.githubusercontent.com/{repo}/{branch}/{it['path']}"
        raw = session.get(raw_url, timeout=DEFAULT_TIMEOUT)
        if raw.status_code != 200:
            continue
        title = Path(it["path"]).stem
        chapters.append(
            Chapter(
                order=i,
                url=f"https://github.com/{repo}/blob/{branch}/{it['path']}",
                title=title,
                markdown=raw.text,
            )
        )
    return chapters


def search_index_chapters(
    index_url: str, site_url: str, session: requests.Session, site_title: str = ""
) -> list[Chapter]:
    """bookdown search_index.json: entries are [href, title, full_text] — the
    book text without any crawling. Filters 404 placeholders and strips the
    'Site Title' prefix bookdown prepends to every page title."""
    r = session.get(index_url, timeout=DEFAULT_TIMEOUT)
    if r.status_code != 200:
        raise RuntimeError(f"GET {index_url} → HTTP {r.status_code}")
    payload = json.loads(r.text)
    if not isinstance(payload, list):
        raise RuntimeError("search_index.json is not a list")
    chapters: list[Chapter] = []
    for i, entry in enumerate(payload, start=1):
        if not isinstance(entry, list) or len(entry) < 3:
            continue
        href, title, text = entry[0], entry[1], entry[2]
        if not isinstance(title, str) or not isinstance(text, str):
            continue
        if re.search(r"page not found|^404\b", title, re.I) or re.search(r"(^|/)404\.html?$", href):
            continue
        full = urljoin(site_url, href)
        clean = title.strip()
        if site_title and clean.startswith(site_title):
            clean = clean[len(site_title):].strip()
        if not clean:
            clean = title.strip()
        chapters.append(Chapter(order=i, url=full, title=clean, markdown=text))
    return chapters


def _parse_sitemap_urls(xml_text: str, base_url: str, session: requests.Session, depth: int = 0) -> list[str]:
    urls: list[str] = []
    root = ET.fromstring(xml_text)
    for child in root:
        tag = child.tag.split("}")[-1]
        if tag != "sitemap" and tag != "url":
            continue
        loc = None
        for sub in child:
            if sub.tag.split("}")[-1] == "loc" and sub.text:
                loc = sub.text.strip()
        if not loc:
            continue
        if tag == "sitemap":
            if depth >= 3:
                continue
            r = session.get(loc, timeout=DEFAULT_TIMEOUT)
            if r.status_code == 200:
                urls.extend(_parse_sitemap_urls(r.text, base_url, session, depth + 1))
        else:
            urls.append(loc)
    return urls


def sitemap_urls(sitemap_url: str, session: requests.Session, prefer_prefix: str = "") -> list[str]:
    """Parse a sitemap (or sitemap index). When the sitemap lists multiple
    site versions (Read the Docs: /en/latest/, /en/stable/, /en/8.x/...) and a
    prefix is given, keep only URLs under that prefix."""
    r = session.get(sitemap_url, timeout=DEFAULT_TIMEOUT)
    if r.status_code != 200:
        raise RuntimeError(f"GET {sitemap_url} → HTTP {r.status_code}")
    urls = _parse_sitemap_urls(r.text, sitemap_url, session)
    if prefer_prefix:
        prefixed = [u for u in urls if urlparse(u).path.startswith(prefer_prefix)]
        if prefixed:
            return prefixed
    return urls


def toc_urls(html: str, base_url: str) -> list[str]:
    """Ordered same-host .html links from the landing page's nav/sidebar.

    Selector ladder: <nav> → known theme containers (.sidebar-tree for Furo,
    .wy-nav-side for Read the Docs, .book-summary for GitBook, .bd-toc, ...) →
    generic container tags whose class/id mention toc/sidebar/menu/contents
    (container tags only, never <svg>) → whole page fallback.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    container = None
    for sel in [
        "nav",
        ".sidebar-tree",
        ".wy-nav-side",
        ".bd-toc",
        ".book-summary",
        "#toc",
        ".toc",
        "#menu",
        ".menu",
        "#contents",
        ".contents",
        "[role='navigation']",
    ]:
        el = soup.select_one(sel)
        if el is not None and el.find("a", href=True):
            container = el
            break
    if container is None:
        container = next(
            (
                t
                for t in soup.find_all(["div", "aside", "nav", "ul", "ol"])
                if any(
                    kw in " ".join(t.get("class") or []).lower()
                    + " " + (t.get("id") or "").lower()
                    for kw in ("toc", "sidebar", "menu", "contents")
                )
                and t.find("a", href=True)
            ),
            soup,
        )
    urls: list[str] = []
    for a in container.find_all("a", href=True):
        full = urljoin(base_url, a["href"])
        if _same_host(base_url, full) and _is_htmlish(full):
            full = _normalize(full)
            if full not in urls:
                urls.append(full)
    return urls


def bfs_urls(
    start_url: str,
    session: requests.Session,
    max_pages: int,
    depth: int,
    include: list[str],
    exclude: list[str],
) -> list[str]:
    visited: set[str] = set()
    queue: deque[tuple[str, int]] = deque([(start_url, 0)])
    pages: list[str] = []
    while queue and len(pages) < max_pages:
        url, d = queue.popleft()
        url = _normalize(url)
        if url in visited:
            continue
        visited.add(url)
        html = fetch_html(url, session)
        if not html:
            continue
        pages.append(url)
        if d >= depth:
            continue
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            full = urljoin(url, a["href"])
            if not _same_host(start_url, full):
                continue
            full = _normalize(full)
            if full in visited or not _is_htmlish(full):
                continue
            if not _passes_filters(full, include, exclude):
                continue
            queue.append((full, d + 1))
    return pages


# ---------------------------------------------------------------------------
# Page → markdown
# ---------------------------------------------------------------------------

def page_markdown(url: str, report: SiteReport, session: requests.Session) -> str:
    """Get one page as clean markdown. Uses a browser (crawl4ai) when the site
    is dynamic, else static extraction."""
    if report.dynamic:
        md = fetch_markdown_with_browser(url)
        if md:
            return strip_nav_furniture(md)
    html = fetch_html(url, session)
    if not html:
        return ""
    return page_to_markdown(html, url)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_inspect(url: str) -> int:
    report = inspect_site(url)
    print(report.to_json())
    return 0


def cmd_crawl(
    url: str,
    outdir: Path,
    strategy: str = "auto",
    max_pages: int = 200,
    depth: int = 2,
    include: Optional[str] = None,
    exclude: Optional[str] = None,
) -> int:
    include_pats = [p for p in (include or "").split(",") if p]
    exclude_pats = [p for p in (exclude or "").split(",") if p]
    session = _session()
    report = inspect_site(url, session)
    chosen = report.strategy if strategy == "auto" else strategy
    if chosen == "unknown":
        print(json.dumps({"error": "inspection failed", "report": report.to_json()}), file=sys.stderr)
        return 1

    chapters: list[Chapter] = []
    if chosen == "source-repo" and report.github_repo:
        chapters = source_repo_chapters(report.github_repo, session)
    elif chosen == "search-index" and report.search_index_url:
        chapters = search_index_chapters(
            report.search_index_url, report.url, session, site_title=report.title or ""
        )
    else:
        if chosen == "sitemap" and report.sitemap_url:
            urls = sitemap_urls(
                report.sitemap_url, session, prefer_prefix=urlparse(report.url).path
            )
            if len(urls) < 5:
                # Version-entry sitemap (Read the Docs lists only the landing
                # page per version) — fall back to the ToC of the current page.
                html = fetch_html(report.url, session)
                urls = toc_urls(html or "", report.url)
        elif chosen == "toc":
            html = fetch_html(report.url, session)
            urls = toc_urls(html or "", report.url)
        elif chosen == "bfs":
            urls = bfs_urls(report.url, session, max_pages, depth, include_pats, exclude_pats)
        else:
            print(json.dumps({"error": f"strategy {chosen} not available for this site"}), file=sys.stderr)
            return 1
        urls = [u for u in urls if _passes_filters(u, include_pats, exclude_pats)]
        for i, u in enumerate(urls[:max_pages], start=1):
            md = page_markdown(u, report, session)
            if not md.strip():
                continue
            chapters.append(Chapter(order=len(chapters) + 1, url=u, title=_guess_title(u, md), markdown=md))

    if not chapters:
        print(json.dumps({"error": "no chapters extracted"}), file=sys.stderr)
        return 1
    metadata = write_corpus(
        chapters,
        outdir,
        site_title=report.title or url,
        site_url=report.url or url,
        generator=report.generator,
        strategy=chosen,
    )
    print(json.dumps({"ok": True, **metadata}, ensure_ascii=False, indent=2))
    return 0


def cmd_page_extract(html_path: Path, out_path: Path) -> int:
    html = html_path.read_text(encoding="utf-8", errors="replace")
    md = page_to_markdown(html, str(html_path))
    out_path.write_text(md, encoding="utf-8")
    print(json.dumps({"ok": True, "output": str(out_path), "chars": len(md)}))
    return 0


def cmd_browser_md(url: str, out: Optional[str] = None) -> int:
    """Render one URL in a real browser (crawl4ai/playwright) and return its
    clean Markdown. Standalone: usable by any workflow for JS-rendered pages.
    Requires the .venv with the crawl extra installed."""
    md = fetch_markdown_with_browser(url)
    if not md:
        print(
            json.dumps(
                {
                    "error": (
                        "browser fetch failed (crawl4ai unavailable or page error). "
                        "Install the crawl extra into .venv: "
                        "scripts/setup-venv.sh"
                    )
                }
            ),
            file=sys.stderr,
        )
        return 1
    md = strip_nav_furniture(md)
    if out:
        Path(out).write_text(md, encoding="utf-8")
        print(json.dumps({"ok": True, "url": url, "output": out, "chars": len(md)}))
    else:
        print(md)
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="site2md", description="Turn a book-like website into a Markdown corpus")
    sub = parser.add_subparsers(dest="command", required=True)

    p_inspect = sub.add_parser("inspect", help="produce a JSON site report")
    p_inspect.add_argument("url")

    p_crawl = sub.add_parser("crawl", help="crawl a site into a book-like corpus")
    p_crawl.add_argument("url")
    p_crawl.add_argument("outdir")
    p_crawl.add_argument("--strategy", default="auto",
                         choices=["auto", "source-repo", "search-index", "sitemap", "toc", "bfs"])
    p_crawl.add_argument("--max-pages", type=int, default=200)
    p_crawl.add_argument("--depth", type=int, default=2)
    p_crawl.add_argument("--include", help="comma-separated fnmatch patterns to keep")
    p_crawl.add_argument("--exclude", help="comma-separated fnmatch patterns to drop")

    p_page = sub.add_parser("page-extract", help="extract one HTML file to clean markdown")
    p_page.add_argument("html")
    p_page.add_argument("out")

    p_fetch = sub.add_parser(
        "browser-md",
        help="render one URL in a browser (crawl4ai) and return clean markdown",
    )
    p_fetch.add_argument("url")
    p_fetch.add_argument("out", nargs="?", help="optional output .md file")

    args = parser.parse_args(argv)
    if args.command == "inspect":
        return cmd_inspect(args.url)
    if args.command == "crawl":
        return cmd_crawl(args.url, Path(args.outdir), args.strategy, args.max_pages, args.depth,
                         args.include, args.exclude)
    if args.command == "page-extract":
        return cmd_page_extract(Path(args.html), Path(args.out))
    if args.command == "browser-md":
        return cmd_browser_md(args.url, args.out)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
