"""Tests for site2md — inspect / extract / assemble / URL-list strategies.

Network is mocked with a fake requests session: tests never hit the internet.
"""

import json
from pathlib import Path

import pytest

from site2md import assemble, cli, extract, inspect


# ---------------------------------------------------------------------------
# Fake network layer
# ---------------------------------------------------------------------------

class FakeResponse:
    def __init__(self, text: str = "", status_code: int = 200, url: str = ""):
        self.text = text
        self.status_code = status_code
        self.url = url

    def json(self):
        return json.loads(self.text)


class FakeSession:
    """Return canned responses. Route keys are either full URLs (exact match)
    or path fragments (segment-level suffix match on the URL path), so
    "/repos/a/b" can never swallow "/repos/a/b/git/trees/..."."""

    def __init__(self, routes: dict[str, FakeResponse]):
        self.routes = routes
        self.headers = {}

    @staticmethod
    def _matches(key: str, url: str) -> bool:
        from urllib.parse import urlparse

        if "://" in key:
            return url.split("#")[0] == key
        up = urlparse(url).path.rstrip("/")
        k = key.rstrip("/")
        return up == k or up.endswith("/" + k.lstrip("/"))

    def get(self, url, timeout=None, **kwargs):
        for key in sorted(self.routes, key=len, reverse=True):
            if self._matches(key, url):
                resp = self.routes[key]
                resp.url = url
                return resp
        return FakeResponse(status_code=404, url=url)


BOOKDOWN_INDEX = """<!DOCTYPE html>
<html><head>
<meta name="generator" content="bookdown 0.46 and GitBook 2.6.7" />
<meta name="github-repo" content="demo/example-book" />
<title>Example Book | Demo</title>
</head><body>
<nav>
<a href="index.html">Preface</a>
<a href="01-intro.html">Introduction</a>
<a href="02-basics.html">Basics</a>
</nav>
<article><h1>Welcome</h1><p>This is the preface of the book.</p></article>
</body></html>"""


# ---------------------------------------------------------------------------
# inspect
# ---------------------------------------------------------------------------

class TestInspect:
    def test_detect_generator_meta(self):
        assert "bookdown" in inspect.detect_generator(BOOKDOWN_INDEX)

    def test_detect_generator_fingerprint(self):
        html = '<html><body><div id="__next">x</div></body></html>'
        assert inspect.detect_generator(html) == "nextjs"

    def test_detect_generator_none(self):
        assert inspect.detect_generator("<html><p>plain</p></html>") is None

    def test_find_github_repo(self):
        assert inspect.find_github_repo(BOOKDOWN_INDEX) == "demo/example-book"
        assert inspect.find_github_repo("<html></html>") is None

    def test_find_page_title(self):
        assert inspect.find_page_title(BOOKDOWN_INDEX) == "Example Book | Demo"

    def test_looks_dynamic_js_shell(self):
        assert inspect.looks_dynamic('<div id="root"></div><script src="/app.js"></script>') is True

    def test_looks_dynamic_static(self):
        assert inspect.looks_dynamic("<article><p>" + "word " * 60 + "</p></article>") is False

    def test_base_dir(self):
        assert inspect._base_dir("https://h/a/b/page.html") == "https://h/a/b"
        assert inspect._base_dir("https://h/rmarkdown-book/") == "https://h/rmarkdown-book"

    def test_discover_resources_subpath(self):
        session = FakeSession(
            {
                "/rmarkdown-book/robots.txt": FakeResponse("User-agent: *\nDisallow: /admin\n"),
                "/rmarkdown-book/search_index.json": FakeResponse(
                    json.dumps([["index.html", "Preface", "text"]]),
                ),
            }
        )
        sm, rb, si, dyn = inspect.discover_resources(
            "https://h/rmarkdown-book/index.html", BOOKDOWN_INDEX, session
        )
        assert sm is None
        assert rb == "https://h/rmarkdown-book/robots.txt"
        assert si == "https://h/rmarkdown-book/search_index.json"
        assert dyn is False

    def test_discover_resources_sitemap_from_robots(self):
        session = FakeSession(
            {
                "/robots.txt": FakeResponse(
                    "Sitemap: https://h/sitemap.xml\n"
                ),
            }
        )
        sm, rb, si, _ = inspect.discover_resources("https://h/", "<html></html>", session)
        assert sm == "https://h/sitemap.xml"

    def test_recommend_strategy_priority(self):
        r = inspect.SiteReport(url="https://h/")
        r.github_repo = "a/b"
        inspect.recommend_strategy(r)
        assert r.strategy == "source-repo"

        r = inspect.SiteReport(url="https://h/")
        r.search_index_url = "https://h/search_index.json"
        inspect.recommend_strategy(r)
        assert r.strategy == "search-index"

        r = inspect.SiteReport(url="https://h/")
        r.sitemap_url = "https://h/sitemap.xml"
        inspect.recommend_strategy(r)
        assert r.strategy == "sitemap"

        r = inspect.SiteReport(url="https://h/")
        r.toc_link_count = 12
        inspect.recommend_strategy(r)
        assert r.strategy == "toc"

        r = inspect.SiteReport(url="https://h/")
        inspect.recommend_strategy(r)
        assert r.strategy == "bfs"

    def test_inspect_site_end_to_end(self):
        session = FakeSession(
            {
                "https://h/": FakeResponse(BOOKDOWN_INDEX),
                "/robots.txt": FakeResponse(""),
                "/sitemap.xml": FakeResponse("", status_code=404),
                "/search_index.json": FakeResponse("", status_code=404),
            }
        )
        report = inspect.inspect_site("https://h/", session=session)
        assert report.generator and "bookdown" in report.generator
        assert report.github_repo == "demo/example-book"
        assert report.strategy == "source-repo"
        assert report.toc_link_count >= 3


# ---------------------------------------------------------------------------
# extract
# ---------------------------------------------------------------------------

class TestExtract:
    def test_bs4_fallback_article(self):
        html = """
        <html><body>
        <nav><a href="/x">Nav</a></nav>
        <header>Site header</header>
        <article><h1>Chapter One</h1><p>Body text here.</p></article>
        <footer>Footer</footer>
        </body></html>
        """
        out = extract._extract_bs4(html)
        assert "Chapter One" in out
        assert "Nav" not in out
        assert "Site header" not in out
        assert "Footer" not in out

    def test_page_to_markdown_keeps_content(self):
        html = "<html><article><h2>Title</h2><p>Some useful words.</p></article></html>"
        md = extract.page_to_markdown(html)
        assert "Title" in md
        assert "Some useful words" in md

    def test_strip_nav_furniture(self):
        md = "content\n[Previous](p.html)\nmore\n[next](n.html)\n"
        out = extract.strip_nav_furniture(md)
        assert "[Previous]" not in out
        assert "[next]" not in out
        assert "content" in out


# ---------------------------------------------------------------------------
# assemble
# ---------------------------------------------------------------------------

class TestAssemble:
    def test_write_corpus(self, tmp_path: Path):
        chapters = [
            assemble.Chapter(order=1, url="https://h/01.html", title="Intro", markdown="hello world"),
            assemble.Chapter(order=2, url="https://h/02.html", title="Basics", markdown="more words here"),
        ]
        meta = assemble.write_corpus(
            chapters, tmp_path, site_title="Demo", site_url="https://h/", strategy="toc"
        )
        assert meta["chapter_count"] == 2
        assert (tmp_path / "sources" / "01-intro.md").exists()
        assert (tmp_path / "sources" / "02-basics.md").exists()
        assert (tmp_path / "metadata.json").exists()
        body = (tmp_path / "sources" / "01-intro.md").read_text(encoding="utf-8")
        assert body.startswith("# Intro")
        assert "Source: https://h/01.html" in body

    def test_slugify(self):
        assert assemble.slugify("Hello, World!") == "hello-world"
        assert assemble.slugify("  R Markdown  ") == "r-markdown"
        assert assemble.slugify("!!!") == "page"


# ---------------------------------------------------------------------------
# cli — URL-list strategies & filters
# ---------------------------------------------------------------------------

class TestCliStrategies:
    def test_noise_filter(self):
        assert cli._passes_filters("https://h/tag/foo", [], []) is False
        assert cli._passes_filters("https://h/logo.png", [], []) is False
        assert cli._passes_filters("https://h/chapter.html", [], []) is True
        assert cli._passes_filters("https://h/page.html?utm_source=x", [], []) is False
        assert cli._passes_filters("https://h/a.html", ["*/a.html"], []) is True
        assert cli._passes_filters("https://h/b.html", [], ["*/b.html"]) is False

    def test_toc_urls_ordered(self):
        urls = cli.toc_urls(BOOKDOWN_INDEX, "https://h/")
        # index.html is normalized to the directory root
        assert urls == ["https://h/", "https://h/01-intro.html", "https://h/02-basics.html"]

    def test_sitemap_nested(self):
        xml = """<?xml version="1.0"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url><loc>https://h/a.html</loc></url>
          <url><loc>https://h/b.html</loc></url>
        </urlset>"""
        session = FakeSession({"https://h/sitemap.xml": FakeResponse(xml)})
        assert cli.sitemap_urls("https://h/sitemap.xml", session) == [
            "https://h/a.html",
            "https://h/b.html",
        ]

    def test_search_index_filters_404_and_prefix(self):
        payload = json.dumps(
            [
                ["index.html", "Demo Book Preface", "preface text"],
                ["404.html", "Page not found", "nope"],
                ["01.html", "Demo Book Chapter", "chapter text"],
            ]
        )
        session = FakeSession({"https://h/search_index.json": FakeResponse(payload)})
        chapters = cli.search_index_chapters(
            "https://h/search_index.json", "https://h/", session, site_title="Demo Book"
        )
        assert len(chapters) == 2
        assert chapters[0].title == "Preface"
        assert chapters[1].title == "Chapter"

    def test_source_repo_chapters(self):
        session = FakeSession(
            {
                "https://api.github.com/repos/a/b": FakeResponse(
                    json.dumps({"default_branch": "main"})
                ),
                "https://api.github.com/repos/a/b/git/trees/main?recursive=1": FakeResponse(
                    json.dumps(
                        {
                            "tree": [
                                {"type": "blob", "path": "01-intro.Rmd"},
                                {"type": "blob", "path": "02-basics.Rmd"},
                                {"type": "blob", "path": "cover.png"},
                                {"type": "blob", "path": ".gitignore"},
                            ]
                        }
                    )
                ),
                "https://raw.githubusercontent.com/a/b/main/01-intro.Rmd": FakeResponse("# Intro\nhello"),
                "https://raw.githubusercontent.com/a/b/main/02-basics.Rmd": FakeResponse("# Basics\nworld"),
            }
        )
        chapters = cli.source_repo_chapters("a/b", session)
        assert [c.title for c in chapters] == ["01-intro", "02-basics"]
        assert "cover.png" not in [c.title for c in chapters]
        assert ".gitignore" not in [c.title for c in chapters]


class TestCli:
    def test_page_extract_command(self, tmp_path: Path):
        src = tmp_path / "in.html"
        src.write_text("<html><body><nav>x</nav><article><h1>T</h1><p>body</p></article></body></html>", encoding="utf-8")
        out = tmp_path / "out.md"
        assert cli.cmd_page_extract(src, out) == 0
        assert "T" in out.read_text(encoding="utf-8")

    def test_guess_title(self):
        assert cli._guess_title("https://h/02-basics.html", "# Basics\n") == "Basics"
        assert cli._guess_title("https://h/02-basics.html", "no heading") == "02 basics"
