# pi-doc-to-skill

> **繁體中文版**: [README_zh.md](README_zh.md)

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

Python dependencies live in a **repo-local virtualenv** (`.venv/`, git-ignored)
so crawl4ai/trafilatura never touch your system Python. One-time setup:

```bash
bash scripts/setup-venv.sh    # .venv + crawl extra + playwright chromium
```

The extension tools pick up `.venv/bin/python` automatically (override with
`SITE2MD_PYTHON`). Static sites need no virtualenv at all — only dynamic
(JS-rendered) sites require it.

## Custom tools

| Tool | Purpose |
|---|---|
| `site_inspect <url>` | Probe the site: generator detection, sitemap / search-index / github-repo discovery, recommended strategy (JSON) |
| `site2md <url> <outdir> [strategy=…]` | Crawl + tidy + assemble a book-like Markdown corpus (`sources/*.md` + `metadata.json`) |
| `page_fetch <url> [out]` | Render one **JS-heavy URL** in a browser (crawl4ai/playwright) → clean Markdown. Standalone, reusable by any skill |
| `page_extract <html> <out.md>` | One HTML file → clean Markdown (trafilatura → bs4) |

Strategies, best first: **source-repo** (public Rmd/MD sources) →
**search-index** (bookdown full text) → **sitemap** (version-aware) → **toc**
(nav links) → **bfs** (bounded crawl). The crawler handles both static sites
(requests + trafilatura, zero heavy deps) and dynamic sites via `page_fetch`
(crawl4ai/playwright).

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

## Relationship to upstream (book-to-skill)

This repository is a **fork** of
[`virgiliojr94/book-to-skill`](https://github.com/virgiliojr94/book-to-skill)
(fork point ≈ upstream commit `b4b3733`, 2026-08-06, just before v1.4.0). The
fork has diverged so far that the two are no longer drop-in interchangeable.
**Local is the source of truth** — the fork was re-initialized as a fresh git
history (no shared ancestry with `origin/master`), so nothing is pushed to
`origin` without a deliberate review.

### Route differences vs. baseline

| Axis | This fork (pi-doc-to-skill) | Baseline (book-to-skill) |
|---|---|---|
| Packaging | Self-contained **pi package** (`pi install`): 2 skills + custom-tools extension | Standalone skill for Copilot CLI / Amp / Claude Code |
| Document conversion | **anydoc** (Firecrawl) at skill level; **OCR fallback** (batch-ocr) for scanned PDFs; quality gate rejects broken conversions | Built-in extractors (pdftotext / pypdf / pdfminer / Docling) |
| Sources | Documents **and book-like websites** (site2md crawler + `site_inspect` / `site2md` / `page_fetch` / `page_extract` tools) | Documents only |
| Skill modes | Explicit **reference (verbatim) / study (distilled)** fork of the pipeline; notes layer in both; verbatim chapter splitting for legal/regulatory text (`scripts/split_reference.py`, fork-only) | Study-focused; text/technical book types + DEPTH axis |
| Generation spec | One shared `docs/skill-generation-spec.md` (Steps 6–10, quality rules) consumed by both skills | Everything in SKILL.md |
| Python setup | Repo-local `.venv` via `scripts/setup-venv.sh`; pyproject with `crawl` extra | System Python, optional packages suggested at runtime |

`CHANGELOG.md` and `PLAN/1_design.md` document the design rationale behind the
divergence.

## License

MIT — see [LICENSE.md](LICENSE.md).
