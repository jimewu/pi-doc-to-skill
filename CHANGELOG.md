# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] — 2026-08-13

### Added

- **pi package** (`pi-doc-to-skill`): bundles two skills + a custom-tools
  extension under one self-contained repository.
- **site-to-skill skill** (new): converts book-like websites into agent
  skills. Pipeline: `site_inspect` → strategy selection → `site2md` crawl →
  corpus → shared generation spec.
- **site2md Python package** (new): site inspection (generator detection,
  sitemap / search-index / github-repo discovery), URL-list strategies
  (source-repo / search-index / sitemap / toc / bfs), main-content extraction
  (trafilatura → bs4 → crawl4ai), corpus assembly with per-chapter source URLs.
- **site-tools pi extension** (new): registers `site_inspect`, `site2md`,
  `page_extract` custom tools.
- **docs/skill-generation-spec.md** (new): shared generation spec (Steps 6–10,
  Update/Fold-in workflow, Quality Rules) — single source of truth consumed by
  both skills.
- Tests for site2md (network mocked); total suite: 315 tests.
- CI: test matrix (py3.9–3.13), ruff, dependency-free smoke (incl. site2md
  page-extract), bandit/zizmor, SKILL.md validation, package manifest check.

### Changed

- Rebased from the book-to-skill 1.3.0 fork: `book_to_skill/`, `scripts/`,
  `tools/`, and their tests were carried over unchanged.
- `book-to-skill` SKILL.md slimmed down: steps 0–5 stay in the skill, steps
  6–10 move to the shared generation spec.
- pyproject: package renamed, added `crawl` extra (crawl4ai, trafilatura).

### Removed

- No longer references the upstream `skill-book-to-skill` repository — this
  package is self-contained.

[2.0.0]: https://github.com/jimewu/pi-doc-to-skill/releases/tag/2.0.0
