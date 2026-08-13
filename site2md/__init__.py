"""site2md — turn a book-like website into a book-like Markdown corpus.

Pipeline stages:
    inspect   → detect generator, discover sitemap/search-index/github-repo
    fetch     → retrieve pages (requests for static, crawl4ai for dynamic)
    extract   → pull the main content (trafilatura → crawl4ai → bs4)
    assemble  → order chapters, write sources/*.md + metadata.json

The output corpus is consumed by the book-to-skill generation phase
(docs/skill-generation-spec.md): sources/*.md feed scripts/extract.py.
"""

__version__ = "2.0.0"
