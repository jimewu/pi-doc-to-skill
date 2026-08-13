# pi-doc-to-skill

Turn **documents** (PDF/EPUB/DOCX/Markdown…) *and* **book-like websites** (docs
sites, online books, course sites) into reusable agent skills — as a single
self-contained [pi](https://github.com/earendil-works/pi-coding-agent) package.

```
book-to-skill:  document (PDF/EPUB/DOCX/…) → convert → corpus ┐
site-to-skill:  website (URL) → inspect → crawl+tidy → corpus ─┤
                                                               ▼
                          docs/skill-generation-spec.md (shared)
                                                               ▼
                                          versioned agent skill
```

## What's inside

| Component | What it does |
|---|---|
| `skills/book-to-skill` | Converts documents into reference (verbatim) or study (distilled) skills |
| `skills/site-to-skill` | Converts book-like **websites** into skills (new) |
| `extensions/site-tools.ts` | pi custom tools behind site-to-skill |
| `site2md/` | Python crawler/tidy package (inspect + crawl + extract + assemble) |
| `book_to_skill/`, `scripts/`, `tools/` | Shared core: extraction, reference splitting, skill scanning/validation |
| `docs/skill-generation-spec.md` | **Shared** generation spec (Steps 6–10) — one file, both skills |

The two skills share everything after the corpus exists: the generation spec,
`scripts/`, `tools/`, the notes layer, and the Quality Rules. They differ only
in how the book-like Markdown is obtained.

## Install

```bash
pi install <path-to-this-repo>      # or: pi install git:github.com/you/pi-doc-to-skill
```

Python dependencies for the site crawler (only needed for **dynamic** /
JS-rendered sites; static sites work with the stdlib + trafilatura path):

```bash
pip install -e "<package-root>[crawl]" && playwright install chromium
```

## Custom tools

| Tool | Purpose |
|---|---|
| `site_inspect <url>` | Probe the site: generator detection, sitemap / search-index / github-repo discovery, recommended strategy (JSON) |
| `site2md <url> <outdir> [strategy=…]` | Crawl + tidy + assemble a book-like Markdown corpus (`sources/*.md` + `metadata.json`) |
| `page_extract <html> <out.md>` | One HTML file → clean Markdown (trafilatura → bs4) |

Strategies, best first: **source-repo** (public Rmd/MD sources) →
**search-index** (bookdown full text) → **sitemap** (version-aware) → **toc**
(nav links) → **bfs** (bounded crawl). The crawler handles both static sites
(requests + trafilatura, zero heavy deps) and dynamic sites (crawl4ai/playwright,
lazy-loaded).

## Quick start

```bash
# 1. Inspect a book-like site
site_inspect https://pkg.yihui.org/rmarkdown-book/
# → generator: bookdown, github_repo: rstudio/rmarkdown-book, strategy: source-repo

# 2. Build the corpus
site2md https://pkg.yihui.org/rmarkdown-book/ /tmp/book --strategy source-repo
# → /tmp/book/sources/*.md + metadata.json

# 3. Hand off to book-to-skill (reference/study) — ask your agent, e.g.:
#    "Turn /tmp/book into a study skill named rmarkdown-guide"
```

## Development

```bash
pip install pytest beautifulsoup4
pytest tests/ -q          # 315 tests, network mocked
ruff check --select E9,F book_to_skill/ site2md/ scripts/ tests/ tools/
```

## License

MIT — see [LICENSE.md](LICENSE.md).
