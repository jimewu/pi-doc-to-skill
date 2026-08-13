---
name: site-to-skill
description: "Converts book-like websites (docs sites, online books, course sites, reference manuals) into versioned agent skills. Runs site_inspect to detect the site's generator and structure (bookdown, Docusaurus, MkDocs, GitBook, ...), picks the best extraction path (GitHub source repo, built-in search index, sitemap, ToC links, or bounded crawl), cleans pages into a book-like Markdown corpus with site2md, then hands off to the shared generation spec for reference (verbatim) or study (distilled) skill output. Use when the user wants to turn a website that reads like a book into a reusable expert or study skill for pi."
metadata:
  version: 2.0.0
  package: pi-doc-to-skill
  spec: docs/skill-generation-spec.md   # generation steps 6-10 live here, shared with book-to-skill
---

<!--
Argument hint: <url-of-the-book-like-site> [skill-name-slug]
Depends on the pi package custom tools: site_inspect, site2md, page_extract.
-->

# Site-to-Skill Converter

Turn a website that reads like a book (chapters, a table of contents, a linear
course) into a reusable agent skill — without manually copying anything.

**The whole trick is the corpus**: the site becomes a book-like Markdown corpus
(`sources/*.md` + `metadata.json`), and from that point on the pipeline is
**identical to book-to-skill**. The generation phase (Steps 6–10) is shared and
lives in a single file:

> **`<package-root>/docs/skill-generation-spec.md`**

Read that spec before generating any skill files (frontmatter schema, verbatim
chapter rules for reference mode, distilled templates for study mode, notes
layer, verification, Quality Rules).

---

## Step 0 — Out-of-scope check

If no URL is provided, respond:

> "site-to-skill requires the URL of a book-like website. Usage: `site-to-skill <url> [skill-name-slug]`"

Book-like means: chapters/sections reachable from a table of contents (docs
sites, online books, tutorials split into pages, standard/reference manuals).
Sites that are **not** book-like — blogs, news portals, community forums,
product landing pages, single-page marketing sites — are out of scope; say so
and stop. If the site is book-like but the user only wants part of it (one
course under `/courses/<topic>/`, a few chapters), note the intended scope for
Step 2 (include/exclude filters).

---

## Step 1 — Inspect the site

Call the **`site_inspect`** tool with the URL. It returns a JSON report:

| Field | Meaning |
|---|---|
| `generator` | Framework: bookdown / Docusaurus / MkDocs / GitBook / Sphinx / Hugo / ... |
| `github_repo` | `<owner>/<repo>` when the page exposes its source repo (bookdown does this) |
| `sitemap_url` | sitemap location, if found (robots.txt or conventional paths) |
| `search_index_url` | bookdown built-in search index (carries the **full text** of every page) |
| `dynamic` | True if the page is JavaScript-rendered (needs a browser) |
| `toc_link_count` | Same-host `.html` links on the landing page (ToC proxy) |
| `strategy` | Recommended extraction strategy + reason |

Read the report **before** crawling — it decides everything downstream.

### Out-of-scope checks after inspection

- `strategy: unknown` (request failed, bot wall, non-HTML) → report and stop.
- Site is a web app behind a login / paywall / heavy anti-bot (anti-bot WAF,
  Cloudflare challenge) → tell the user; try a mirror or ask them to download
  the content. Do not try to bypass access controls.

---

## Step 2 — Choose the strategy (confirm with the user)

The strategies are ordered by quality — **best first**:

| # | Strategy | When | What you get |
|---|---|---|---|
| 1 | `source-repo` | `github_repo` present | The book's Rmd/MD **sources** — cleanest possible corpus |
| 2 | `search-index` | `search_index_url` present | bookdown full text per page — no crawling at all |
| 3 | `sitemap` | `sitemap_url` present | URL list from the sitemap |
| 4 | `toc` | `toc_link_count >= 5` | Ordered links from the landing page nav |
| 5 | `bfs` | nothing else | Bounded same-host crawl (depth/limit) |

Defaults to the inspection's recommendation. Confirm with the user when the
choice is not obvious (e.g. `source-repo` exists but the repo is stale vs. the
site; or the user wants a specific scope). Also decide the **scope** here:

- **Whole site**: no filters.
- **Part of the site** (e.g. only `/docs/getting-started/...`): pass
  `--include '*/docs/getting-started/*'` (fnmatch patterns) or `--exclude`
  for the parts to skip (news, blog, version archives).

---

## Step 3 — Build the corpus

Call the **`site2md`** tool:

```
site2md url=<url> outdir=<workdir/corpus> [strategy=...] [maxPages=...] [depth=...] [include=...] [exclude=...]
```

Choose `<workdir>` with enough space (a few hundred pages × ~5 KB/page ≈ a few
MB). The tool writes:

```
<outdir>/
├── metadata.json       # title, generator, strategy, per-chapter URLs & tokens
└── sources/
    ├── 01-<slug>.md    # one file per chapter, ordered
    └── ...
```

Each chapter file carries its **source URL** in a `Source:` line — keep it:
the generated skill cites it, and Step 4 verification uses it.

**Dynamic sites** (`dynamic: true`, or empty results from the static path):
`site2md` falls back to a browser via crawl4ai. That dependency is optional —
install once:

```bash
pip install -e "<package-root>[crawl]" && playwright install chromium
```

If the crawl yields very little (e.g. only the landing page), the site is
probably JS-rendered: install the crawl extra and re-run.

---

## Step 4 — Quality gate (before generating anything)

Garbage in, garbage out — same rule as book-to-skill's conversion gate:

1. **Read `metadata.json`**: `chapter_count`, `total_tokens`, per-chapter
   `tokens`. A book with 5 chapters and 12K tokens is plausible; 1 chapter
   from a 30-chapter site is a failure.
2. **Spot-check 2–3 chapters** against their live URLs (the `Source:` line):
   - Content matches the page (right topic, right order).
   - Tidy is neither too aggressive (article body gone) nor too weak (nav
     text, "Previous/Next", cookie banners, comments leaking into the text).
   - `search-index` corpora: bookdown full text is included verbatim — check
     code blocks survived.
3. **Chapter order** follows the book's ToC (search-index and sitemap keep
   site order; if it is wrong, re-run with an explicit strategy or ask the
   user for the intended order and renumber the files manually — the
   generation phase trusts `sources/` order as the chapter order).
4. **Scope** matches what the user asked (include/exclude honored).

Fix problems by re-running `site2md` with different options (`--strategy`,
`--include/--exclude`, `--max-pages`), or clean individual files by hand with
the **`page_extract`** tool. Do **not** proceed to generation with a broken
corpus.

---

## Step 5 — Choose mode and hand off to generation

Ask the user the same question book-to-skill asks (reference vs study), then
run the **shared generation spec** (`docs/skill-generation-spec.md`):

- **reference** — verbatim knowledge base (regulations, standards, API specs,
  reference manuals published online): exact wording preserved, chapter files
  quote the site verbatim, each file keeps its source URL.
- **study** — distilled learning material (online courses, tutorials,
  textbooks-as-sites): frameworks, takeaways, glossary, cheatsheet.

Hand-off mechanics (the corpus is Markdown, so it plugs into the existing
pipeline unchanged):

1. Feed `sources/*.md` to the shared extract step the same way book-to-skill
   does (or point `BOOK_SKILL_WORKDIR` at the corpus directory).
2. Steps 6–10 of the spec: skill directory structure, chapter generation
   (verbatim split or distilled), supporting files, notes layer, master
   SKILL.md, verification, cleanup — **identical for both skills**.
3. In the generated SKILL.md frontmatter, record the source as the site URL
   (`sources[].name` = site title, `kind: website`, `version: <accessed
   date>`, `notes` = generator + strategy used). The `Source:` URL lines make
   every quote verifiable against the live page.

---

## Locate the package

The custom tools resolve the package root themselves; you only need it for the
shared spec and the helper scripts (`scripts/extract.py`,
`scripts/split_reference.py`, `tools/scan_generated_skill.py`). Probe in order:

```bash
PACKAGE_ROOT=""
for candidate in \
  "$HOME/.agents/skills/site-to-skill/.." \
  "$HOME/.pi/agent/skills/site-to-skill/.." \
  "$HOME/.pi/agent/git/"*"/pi-doc-to-skill" \
  "$HOME/.pi/agent/npm/"*"/pi-doc-to-skill" \
  "$HOME/.pi/agent/npm/node_modules/pi-doc-to-skill" \
  ".pi/skills/site-to-skill/.." \
  ".agents/skills/site-to-skill/.."
do
  if [ -f "$candidate/docs/skill-generation-spec.md" ]; then
    PACKAGE_ROOT="$(cd "$candidate" && pwd)"
    break
  fi
done
```

Then: spec = `$PACKAGE_ROOT/docs/skill-generation-spec.md`, scripts =
`$PACKAGE_ROOT/scripts/`, tools = `$PACKAGE_ROOT/tools/`.

---

## Relationship to book-to-skill

Both skills live in the same package and share **everything after the corpus
exists**: the generation spec, `scripts/`, `tools/`, the notes layer, and the
Quality Rules. They differ only in Step 0–4 — how the book-like Markdown is
obtained:

```
book-to-skill:  document (PDF/EPUB/DOCX/...) → convert → corpus
site-to-skill:  website (URL) → inspect → crawl+tidy → corpus
                                   ↓
              docs/skill-generation-spec.md (shared Steps 6–10)
                                   ↓
                          versioned agent skill
```

You may freely route between them: a corpus produced by `site2md` can be
handed to book-to-skill, and a downloaded page collection can be treated as
site sources.
