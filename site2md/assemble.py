"""Assemble crawled pages into a book-like Markdown corpus.

Output layout (consumed by book-to-skill's generation phase):

    <outdir>/
    ├── metadata.json          # title, strategy, per-chapter source URLs & tokens
    └── sources/
        ├── 01-introduction.md # one file per chapter, ordered
        └── ...

Every chapter file keeps its source URL so the generated skill can cite it and
the agent can verify a quote against the live page.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:  # CJK-aware token estimate shared with book_to_skill
    from book_to_skill.utils import estimate_tokens
except ImportError:  # pragma: no cover - standalone use
    def estimate_tokens(text: str) -> int:
        return max(1, int(len(text.split()) / 0.75))


def slugify(name: str) -> str:
    s = re.sub(r"[^\w\s-]", "", name.lower())
    s = re.sub(r"[\s_]+", "-", s).strip("-")
    return s or "page"


@dataclass
class Chapter:
    order: int
    url: str
    title: str
    markdown: str

    @property
    def slug(self) -> str:
        return f"{self.order:02d}-{slugify(self.title)}"


def _chapter_header(chapter: Chapter) -> str:
    title = chapter.title.strip() or chapter.url
    return f"# {title}\n\nSource: {chapter.url}\n\n"


def write_corpus(
    chapters: list[Chapter],
    outdir: Path,
    *,
    site_title: str = "",
    site_url: str = "",
    generator: Optional[str] = None,
    strategy: str = "",
) -> dict:
    """Write sources/*.md + metadata.json. Returns the metadata dict."""
    outdir = Path(outdir)
    sources = outdir / "sources"
    sources.mkdir(parents=True, exist_ok=True)

    meta_chapters: list[dict] = []
    total_tokens = 0
    for chapter in chapters:
        body = _chapter_header(chapter) + chapter.markdown.strip() + "\n"
        target = sources / f"{chapter.slug}.md"
        target.write_text(body, encoding="utf-8")
        tokens = estimate_tokens(body)
        total_tokens += tokens
        meta_chapters.append(
            {
                "order": chapter.order,
                "slug": chapter.slug,
                "title": chapter.title.strip() or chapter.url,
                "url": chapter.url,
                "file": f"sources/{target.name}",
                "tokens": tokens,
            }
        )

    metadata = {
        "title": site_title,
        "url": site_url,
        "generator": generator,
        "strategy": strategy,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "chapter_count": len(chapters),
        "total_tokens": total_tokens,
        "chapters": meta_chapters,
    }
    (outdir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return metadata
