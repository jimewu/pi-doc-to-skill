#!/usr/bin/env python3
"""
Split a converted-Markdown source into verbatim per-chapter Markdown files.

Used by book-to-skill reference mode. Given full_text.txt (extract.py output,
optionally multi-source with SOURCE: banners), detect top-level Chapter/Annex
headings, skip the table of contents heuristically, and write one file per
heading preserving the ORIGINAL TEXT verbatim.

Three-level progressive disclosure (reference mode):

    L0  SKILL.md                    — Document Map (Chapter → index file)
    L1  indexes/ch<NN>-index.md     — per-chapter sub-index: articles → files
    L2  chapters/ch<NN>-art-<NN>.md — actual content (article- or cluster-level)

Whether L1/L2 apply depends on length (--granularity auto):
  - chapter tokens <= --max-chapter-tokens (default 4000) → one file per
    chapter, no index layer (current single-file behavior)
  - chapter tokens >  threshold → the chapter is split into article-level
    files under chapters/, plus an index under indexes/. Oversized articles
    (> --max-file-tokens, default 3000) are split further by their internal
    numbered items.

Definition-style articles (e.g. MDR Art 2) can be clustered by topic: pass
--clusters-file with a YAML/JSON list of clusters (article + item ranges); the
script writes one file per cluster instead of one file per article.

The only additions to the source text are, per output file: an H1 title, a
one-line `Source:` note, and an article/section index block. Everything below
is the source text as written — never paraphrased. Split lines never cut
inside a paragraph, so every file stays independently citable.

Supports English ("CHAPTER I", "Chapter 1:", "ANNEX I", "## Chapter 2") and
CJK ("第一章", "第2章", "附錄A") heading styles, with optional Markdown heading
prefixes.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Ensure the repo root (where the book_to_skill package lives) is importable,
# so we can reuse the CJK-aware token estimator.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from book_to_skill.utils import estimate_tokens
except ImportError:  # pragma: no cover - fallback for standalone use
    def estimate_tokens(text: str) -> int:
        return max(1, int(len(text.split()) / 0.75))


# ---------------------------------------------------------------------------
# Heading detection
# ---------------------------------------------------------------------------

_TOP_HEADING = re.compile(
    r"^(#{1,6}\s+|\*)?(?P<kind>chapter|annex|part)\s+"
    r"(?P<num>[0-9IVXLCDM]+|[A-Z](?![A-Z]))\*?"
    r"(?P<rest>.*)$",
    re.IGNORECASE,
)
_CJK_TOP_HEADING = re.compile(
    r"^(#{1,6}\s+|\*)?(?P<kind>第[一二三四五六七八九十百千0-9]+)(?P<unit>[章篇])\*?"
    r"(?P<rest>.*)$",
)
_CJK_ANNEX_HEADING = re.compile(
    r"^(#{1,6}\s+|\*)?(附錄|附录|附件)\s*(?P<num>[A-Z0-9一二三四五六七八九十]+)?\*?"
    r"(?P<rest>.*)$",
)

_ARTICLE_HEADING = re.compile(
    r"^(#{1,6}\s+)?article\s+(?P<num>[0-9]+)(?P<rest>.*)$",
    re.IGNORECASE,
)
_CJK_ARTICLE_HEADING = re.compile(
    r"^(#{1,6}\s+)?第(?P<num>[0-9一二三四五六七八九十百千]+)條(?P<rest>.*)$",
)

# Item headings inside an article: "(1) ..." (legal style) or "1. ..." / "1.1. ...",
# optionally with a Markdown heading prefix ("### 1. ORGANISATIONAL ...").
_ITEM_PAREN = re.compile(r"^(#{1,6}\s+)?\((?P<num>[0-9]+)\)\s+(?P<rest>.*)$")
_ITEM_DOT = re.compile(r"^(#{1,6}\s+)?(?P<num>[0-9]+(?:\.[0-9]+)*)[.)]\s+(?P<rest>.*)$")

_SOURCE_BANNER = re.compile(r"^SOURCE:\s*(?P<name>.*)$")
_BANNER_LINE = re.compile(r"^=+$")

DEFAULT_MAX_CHAPTER_TOKENS = 4000
DEFAULT_MAX_FILE_TOKENS = 3000


def _clean_title(rest: str) -> str:
    """Normalize a heading's trailing text into a short title fragment."""
    rest = rest.strip()
    rest = re.sub(r"^[\s.:：\-—–\t]+", "", rest)
    rest = re.sub(r"[\s.:：\-—–\t]+$", "", rest)
    return rest


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def find_top_headings(lines: list[str]) -> list[tuple[int, str, str, bool]]:
    """Return [(line_index, kind, title_text, annex_internal), ...].

    Matches CHAPTER/PART/ANNEX headings (English + CJK, optional Markdown
    heading prefix or italic wrapping such as "*ANNEX I*"). The last element
    is always False here — annex context is computed by the caller AFTER the
    table of contents has been filtered (a ToC may list "ANNEX I" before any
    body content, which must not demote the main-body chapters).
    """
    headings: list[tuple[int, str, str, bool]] = []
    for i, line in enumerate(lines):
        s = line.strip()
        if not s or len(s) > 120:
            continue
        m = _TOP_HEADING.match(s)
        if m:
            kind = m.group("kind").lower()
            num = m.group("num").upper()
            rest_raw = m.group("rest")
            # A line that starts a real heading does not continue a sentence:
            # "Annex XVI, taking into account the state of the art, ..." is body
            # text (continuation of a sentence naming the annex), not a heading.
            if rest_raw.startswith((",", ";", ".")):
                continue
            rest = _clean_title(rest_raw)
            if kind == "annex":
                title = f"ANNEX {num}" + (f" — {rest}" if rest else "")
            else:
                title = f"{kind.title()} {num}" + (f" — {rest}" if rest else "")
            headings.append((i, kind, title, False))
            continue
        m = _CJK_TOP_HEADING.match(s)
        if m:
            title = m.group("kind") + m.group("unit") + (
                f" — {_clean_title(m.group('rest'))}" if m.group("rest").strip() else ""
            )
            headings.append((i, "chapter", title, False))
            continue
        m = _CJK_ANNEX_HEADING.match(s)
        if m:
            title = "附錄" + (m.group("num") or "") + (
                f" — {_clean_title(m.group('rest'))}" if m.group("rest").strip() else ""
            )
            headings.append((i, "annex", title, False))
    return headings


def find_articles(lines: list[str], start: int, end: int) -> list[tuple[str, str, int]]:
    """Return [(num, title, line_offset_within_slice), ...] for Article headings.

    ``line_offset`` is relative to ``start`` (so slicing works on the same
    list the caller passes in).
    """
    articles: list[tuple[str, str, int]] = []
    for off, line in enumerate(lines[start:end]):
        s = line.strip()
        if not s or len(s) > 120:
            continue
        m = _ARTICLE_HEADING.match(s)
        if m:
            title = _clean_title(m.group("rest"))
            if not title:
                # The article title may sit on the next heading line, e.g.
                # "## Article 2" followed by "## Definitions" (OCR output).
                title = _following_heading_title(lines, start + off + 1, end)
            articles.append((m.group("num"), title, off))
            continue
        m = _CJK_ARTICLE_HEADING.match(s)
        if m:
            title = _clean_title(m.group("rest"))
            if not title:
                title = _following_heading_title(lines, start + off + 1, end)
            articles.append((m.group("num"), title, off))
    return articles


def _following_heading_title(lines: list[str], from_line: int, end: int) -> str:
    """Return the title text of the next heading-like line, if any.

    Handles OCR layouts where the article number and its title are separate
    headings ("## Article 2" then "## Definitions"). The next non-empty line
    counts if it is a Markdown heading, a short ALL-CAPS line, or a short
    Title-Case line that does not end in sentence punctuation. Stops at the
    next Article heading (the title belongs to the current article only).
    """
    for nxt in lines[from_line:end]:
        ns = nxt.strip()
        if not ns:
            continue
        if _ARTICLE_HEADING.match(ns) or _CJK_ARTICLE_HEADING.match(ns):
            return ""
        candidate = ns.lstrip("#").strip()
        if ns.startswith("#") and candidate:
            return _clean_title(candidate)
        if (
            len(ns) <= 60
            and not ns.endswith((".", ";", ":"))
            and not ns[0].isdigit()
        ):
            return _clean_title(ns)
        return ""
    return ""


def find_items(section: list[str]) -> list[tuple[int, int, str]]:
    """Return [(num, line_index, title), ...] for item headings in a section.

    Matches legal-style "(1) ..." (definition items — kept even when long) and
    numbered headings "1." / "1.1.". Numbered headings must LOOK like
    headings: a short line (<= 80 chars) that does not end in sentence
    punctuation, so numbered paragraphs such as "1.1.1. Each notified body
    shall be established under the national law of a Member State, ..." are
    NOT treated as split points. Returns the leading integer as the number.
    """
    items: list[tuple[int, int, str]] = []
    for idx, line in enumerate(section):
        s = line.strip()
        if not s:
            continue
        m = _ITEM_PAREN.match(s)
        if m:
            items.append((int(m.group("num")), idx, _clean_title(m.group("rest"))))
            continue
        m = _ITEM_DOT.match(s)
        if m and len(s) <= 80 and not s.rstrip().endswith((".", ";", ":")):
            items.append((int(m.group("num").split(".")[0]), idx, _clean_title(m.group("rest"))))
    return items


def filter_toc(headings: list[tuple[int, str, str, bool]], lines: list[str], min_gap: int) -> list[tuple[int, str, str, bool]]:
    """Drop the table-of-contents run at the head of the document."""
    if len(headings) < 2:
        return headings
    for idx, (ln, _k, _t, _ai) in enumerate(headings):
        end = headings[idx + 1][0] if idx + 1 < len(headings) else len(lines)
        gap = sum(len(lines[j]) + 1 for j in range(ln, end))
        if gap >= min_gap:
            return headings[idx:]
    return headings


def detect_sources(lines: list[str]) -> dict[int, str]:
    """Map line_index -> source label for lines that begin a SOURCE: banner."""
    sources: dict[int, str] = {}
    for i, line in enumerate(lines):
        if _BANNER_LINE.match(line.strip()):
            if i + 1 < len(lines):
                m = _SOURCE_BANNER.match(lines[i + 1].strip())
                if m:
                    sources[i] = m.group("name").strip()
    return sources


# ---------------------------------------------------------------------------
# Cluster definitions (--clusters-file)
# ---------------------------------------------------------------------------

def load_clusters(path: str) -> list[dict]:
    """Load cluster definitions from a JSON or YAML file.

    Expected shape::

        clusters:
          - chapter: 1                    # 1-based chapter number (ch01)
            file: ch01-defs-economic       # output file name (no dir/extension)
            parts: ["art-2:1-10", "art-3"] # article + optional item range
          - chapter: 1
            file: ch01-defs-devices
            parts: ["art-2:11-25"]

    ``parts`` syntax: ``art-<N>`` (whole article) or ``art-<N>:<start>-<end>``
    (article item range). Each cluster becomes one verbatim file.
    """
    text = Path(path).read_text(encoding="utf-8")
    if path.lower().endswith(".json"):
        data = json.loads(text)
    else:
        try:
            import yaml  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise SystemExit(
                "clusters-file: PyYAML is required for .yaml files (pip3 install pyyaml)"
            ) from exc
        data = yaml.safe_load(text)
    return data.get("clusters", data) if isinstance(data, dict) else data


_PART_RE = re.compile(r"^art-(?P<article>[0-9]+)(:(?P<start>[0-9]+)-(?P<end>[0-9]+))?$")


def _match_part(part: str, anum: str, items: list[tuple[int, int, str]]) -> list[int]:
    """Return the item line indexes of ``part`` within an article's items.

    ``part`` is ``art-N`` (all items) or ``art-N:start-end`` (item range).
    Returns [] if the article number does not match or the range is empty.
    """
    m = _PART_RE.match(part)
    if not m:
        return []
    if int(m.group("article")) != int(anum):
        return []
    if not items:
        return []
    if m.group("start") is None:
        return [idx for _n, idx, _t in items]
    start, end = int(m.group("start")), int(m.group("end"))
    return [idx for n, idx, _t in items if start <= n <= end]


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _write_file(out_path: Path, header: list[str], body: list[str], overwrite: bool) -> bool:
    if out_path.exists() and not overwrite:
        return False
    out_path.write_text("\n".join(header + body) + "\n", encoding="utf-8")
    return True


def _make_header(title: str, source_label: str, index_lines: list[str]) -> list[str]:
    return [
        f"# {title}",
        f"Source: {source_label}, {title}",
        "",
        *index_lines,
        "",
        "---",
        "",
    ]


def _article_index_lines(articles: list[tuple[str, str, int]]) -> list[str]:
    if not articles:
        return ["> *(no Article headings detected in this section)*"]
    if len(articles) == 1:
        rng = articles[0][0]
    else:
        rng = f"{articles[0][0]}–{articles[-1][0]}"
    lines = [f"> **Article Index**: Articles {rng}"]
    for anum, atitle, _off in articles:
        lines.append(f"> - Art {anum}" + (f" — {atitle}" if atitle else ""))
    return lines


def _item_index_lines(items: list[tuple[int, int, str]]) -> list[str]:
    if not items:
        return ["> *(no numbered items detected in this section)*"]
    lines = ["> **Item Index**: " + ", ".join(str(n) for n, _i, _t in items[:12])]
    if len(items) > 12:
        lines[0] += ", …"
    for n, _i, t in items:
        lines.append(f"> - {n}. " + (t if t else ""))
    return lines


def _trim_trailing_banners(section: list[str]) -> list[str]:
    while section and (
        not section[-1].strip()
        or _BANNER_LINE.match(section[-1].strip())
        or _SOURCE_BANNER.match(section[-1].strip())
    ):
        section.pop()
    return section


# ---------------------------------------------------------------------------
# Splitting
# ---------------------------------------------------------------------------

def split_single_chapter(
    num: int, title: str, section: list[str], source_label: str,
    out_dir: Path, overwrite: bool,
) -> tuple[str, bool]:
    """Write one verbatim file per chapter (short chapters). Returns (name, written)."""
    articles = find_articles(section, 0, len(section))
    slug = _slugify(title.split(" — ", 1)[-1]) if " — " in title else _slugify(title)
    fname = f"ch{num:02d}" + (f"-{slug}" if slug else "") + ".md"
    header = _make_header(title, source_label, _article_index_lines(articles))
    written = _write_file(out_dir / fname, header, _trim_trailing_banners(section), overwrite)
    return fname, written


def split_articles_chapter(
    num: int, title: str, kind: str, section: list[str], source_label: str,
    chapters_dir: Path, indexes_dir: Path,
    max_file_tokens: int, clusters: list[dict] | None, overwrite: bool,
    annex_sections: list[tuple[int, str]] | None = None,
) -> tuple[list[str], bool]:
    """Split a long chapter or annex into subunit files + an L1 index file.

    Subunits are Article headings for main-body chapters, or annex-internal
    CHAPTER/PART headings (``annex_sections``, relative line offsets) for
    annexes. Returns (written_file_names, any_written).
    """
    annex_sections = annex_sections or []
    articles = find_articles(section, 0, len(section))
    written_files: list[str] = []
    any_written = False

    is_annex_split = kind == "annex"
    cluster_for = {int(cl["chapter"]): cl for cl in clusters or []}
    cluster_def = cluster_for.get(num)

    if cluster_def and not is_annex_split:
        # Cluster mode: write one file per cluster definition.
        for cl in cluster_def.get("clusters", []):
            cl_name = cl.get("file") or f"ch{num:02d}-cluster"
            parts: list[str] = cl.get("parts", [])
            collected: list[str] = []
            idx_lines: list[str] = []
            art_seen: list[str] = []
            for anum, atitle, aoff in articles:
                aend = _article_end(section, articles, aoff)
                art_section = section[aoff:aend]
                items = find_items(art_section)
                hit = _match_part_any(parts, anum, items)
                if hit is not None:
                    art_seen.append(anum)
                    if hit == "all":
                        body = art_section
                    else:
                        body = _item_slice(art_section, hit)
                    idx_lines.append(f"> - Art {anum}" + (f" — {atitle}" if atitle else ""))
                    collected.extend(body)
            fname = f"{cl_name}.md"
            header = _make_header(title, source_label, idx_lines or ["> *(empty cluster)*"])
            if _write_file(chapters_dir / fname, header, _trim_trailing_banners(collected), overwrite):
                written_files.append(fname)
                any_written = True
        index_rows = _cluster_index_rows(cluster_def, written_files)
    else:
        # Subunit mode: one file per article (main chapters) or per annex
        # subunit (annex-internal sections, or numbered items, or the whole
        # annex); oversized subunits split by their numbered items.
        if is_annex_split:
            if annex_sections:
                subunits: list[tuple[str, str, int]] = [
                    ("section", stitle, soff) for soff, stitle in annex_sections
                ]
            else:
                annex_items = find_items(section)
                if annex_items:
                    # Group items by their leading number: all "1.", "1.1.", "1.2." …
                    # items belong to one file (sub-numbered paragraphs stay with
                    # their parent section). The subunit range starts at the first
                    # item of each group.
                    first_of: dict[int, tuple[int, str]] = {}
                    for n, idx, t in annex_items:
                        first_of.setdefault(n, (idx, t))
                    subunits = [
                        (f"item-{n}", t or f"item {n}", idx)
                        for n, (idx, t) in sorted(first_of.items())
                    ]
                else:
                    subunits = [("whole", title, 0)]
        else:
            subunits = [(anum, atitle, aoff) for anum, atitle, aoff in articles]
        index_rows: list[tuple[str, str]] = []
        for idx, (slabel, stitle, soff) in enumerate(subunits):
            send = len(section)
            for slabel2, stitle2, soff2 in subunits:
                if soff2 > soff:
                    send = soff2
                    break
            sub_section = section[soff:send]
            sub_tokens = estimate_tokens("\n".join(sub_section))
            items = find_items(sub_section)
            if is_annex_split:
                if slabel == "section":
                    slug = _slugify(stitle.split(" — ", 1)[-1]) if " — " in stitle else _slugify(stitle)
                    fname = f"ch{num:02d}" + (f"-{slug}" if slug else f"-sec-{idx+1:02d}") + ".md"
                    hdr_idx = [f"> - {stitle}"]
                    row_label = stitle
                elif slabel == "whole":
                    slug = _slugify(stitle.split(" — ", 1)[-1]) if " — " in stitle else _slugify(stitle)
                    fname = f"ch{num:02d}" + (f"-{slug}" if slug else "") + ".md"
                    hdr_idx = [f"> - {stitle}"]
                    row_label = stitle
                else:  # item fallback: slabel is "item-<n>"
                    slug = f"item-{slabel.removeprefix('item-')}"
                    fname = f"ch{num:02d}-{slug}.md"
                    hdr_idx = [f"> - {stitle}"]
                    row_label = stitle
            else:
                slug = _slugify(stitle)
                fname = f"ch{num:02d}-art-{slabel}" + (f"-{slug}" if slug else "") + ".md"
                hdr_idx = [f"> - Art {slabel}" + (f" — {stitle}" if stitle else "")]
                row_label = f"Art {slabel}" + (f" — {stitle}" if stitle else "")
            if sub_tokens > max_file_tokens and items and not is_annex_split:
                pieces = _split_items_into_files(sub_section, items, max_file_tokens)
                for pidx, (pitems, pbody) in enumerate(pieces, start=1):
                    pnums = ", ".join(str(n) for n, _i, _t in pitems)
                    pfname = f"ch{num:02d}-art-{slabel}-part-{pidx}.md"
                    header = _make_header(
                        f"{title} — Art {slabel} (items {pnums})", source_label,
                        hdr_idx + [f"> - Items: {pnums}"],
                    )
                    if _write_file(chapters_dir / pfname, header, _trim_trailing_banners(pbody), overwrite):
                        written_files.append(pfname)
                        any_written = True
                        index_rows.append((f"{row_label} (items {pnums})", pfname))
            else:
                header = _make_header(
                    (f"{title} — {row_label}" if is_annex_split else
                     f"{title} — Art {slabel}" + (f": {stitle}" if stitle else "")),
                    source_label, hdr_idx,
                )
                if _write_file(chapters_dir / fname, header, _trim_trailing_banners(sub_section), overwrite):
                    written_files.append(fname)
                    any_written = True
                    index_rows.append((row_label, fname))

    # L1 index file (created lazily so --granularity chapter leaves no empty dir).
    indexes_dir.mkdir(parents=True, exist_ok=True)
    idx_name = f"ch{num:02d}-index.md"
    idx_header = [
        f"# {title} — Index",
        f"Source: {source_label}, {title}",
        "",
        "> This chapter is split into on-demand files. Read the file for the",
        "> article you need; never load the whole chapter at once.",
        "",
        "## Topics",
        "<!-- Sub-topic → articles → files. The generating agent fills this table",
        "     per SKILL.md Step 8 (read the article titles below, group them by",
        "     subject, link each topic to the exact article files). This is what",
        "     lets a reader go straight to the relevant articles instead of",
        "     loading the whole chapter. -->",
        "",
        "| Topic | Articles → Files |",
        "|-------|------------------|",
        "",
        "## Articles",
        f"| File | Articles |",
        f"|------|----------|",
    ]
    for label, fname in index_rows:
        idx_header.append(f"| [{fname}]({fname}) | {label} |")
    idx_header.extend(["", "---", ""])
    if _write_file(indexes_dir / idx_name, idx_header, [], overwrite):
        any_written = True
    return written_files, any_written


def _article_end(section: list[str], articles: list[tuple[str, str, int]], aoff: int) -> int:
    for nxt_anum, _t, nxt_off in articles:
        if nxt_off > aoff:
            return nxt_off
    return len(section)


def _match_part_any(parts: list[str], anum: str, items: list[tuple[int, int, str]]) -> str | list[int] | None:
    """Match an article against the cluster parts; returns 'all', item indexes, or None."""
    hits: list[int] = []
    for part in parts:
        m = _PART_RE.match(part)
        if not m or int(m.group("article")) != int(anum):
            continue
        if m.group("start") is None:
            return "all"
        start, end = int(m.group("start")), int(m.group("end"))
        hits.extend(idx for n, idx, _t in items if start <= n <= end)
    if not hits:
        return None
    return sorted(set(hits))


def _item_slice(art_section: list[str], indexes: list[int]) -> list[str]:
    """Return the lines of art_section belonging to the given item line indexes.

    ``indexes`` are line indexes as returned by ``_match_part_any`` (i.e.
    positions within ``art_section``). Includes each item heading line and its
    following content until the next item heading or the end of the article.
    """
    items = find_items(art_section)
    wanted = set(indexes)
    out: list[str] = []
    for _n, idx, _t in items:
        if idx not in wanted:
            continue
        end = len(art_section)
        for _n2, idx2, _t2 in items:
            if idx2 > idx:
                end = idx2
                break
        out.extend(art_section[idx:end])
    return out


def _split_items_into_files(
    art_section: list[str], items: list[tuple[int, int, str]], max_file_tokens: int
) -> list[tuple[list[tuple[int, int, str]], list[str]]]:
    """Greedily pack items into files so each stays under max_file_tokens."""
    pieces: list[tuple[list[tuple[int, int, str]], list[str]]] = []
    cur_items: list[tuple[int, int, str]] = []
    cur_lines: list[str] = []
    cur_tokens = 0
    for i, (n, idx, t) in enumerate(items):
        end = items[i + 1][1] if i + 1 < len(items) else len(art_section)
        item_lines = art_section[idx:end]
        item_tokens = estimate_tokens("\n".join(item_lines))
        if cur_items and cur_tokens + item_tokens > max_file_tokens:
            pieces.append((cur_items, cur_lines))
            cur_items, cur_lines, cur_tokens = [], [], 0
        cur_items.append((n, idx, t))
        cur_lines.extend(item_lines)
        cur_tokens += item_tokens
    if cur_items:
        pieces.append((cur_items, cur_lines))
    return pieces


def _cluster_index_rows(cluster_def: dict, written_files: list[str]) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for cl in cluster_def.get("clusters", []):
        fname = f"{cl.get('file')}.md"
        if fname in written_files:
            label = cl.get("label") or cl.get("name") or fname
            rows.append((label, fname))
    return rows


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="split_reference.py",
        description=__doc__.splitlines()[0],
    )
    ap.add_argument("input", help="full_text.txt (or any converted Markdown source)")
    ap.add_argument("-o", "--output-dir", default="chapters",
                    help="L2 content directory (default: chapters)")
    ap.add_argument("--index-dir", default="indexes",
                    help="L1 index directory (default: indexes)")
    ap.add_argument("--granularity", choices=["chapter", "article", "auto"], default="auto",
                    help="chapter = one file per chapter (no L1/L2); article = always split "
                         "long chapters into article files; auto = split only chapters over "
                         "--max-chapter-tokens (default: auto)")
    ap.add_argument("--max-chapter-tokens", type=int, default=DEFAULT_MAX_CHAPTER_TOKENS,
                    help=f"chapter token threshold for enabling L1/L2 (default: {DEFAULT_MAX_CHAPTER_TOKENS})")
    ap.add_argument("--max-file-tokens", type=int, default=DEFAULT_MAX_FILE_TOKENS,
                    help=f"per-file token ceiling for article files (default: {DEFAULT_MAX_FILE_TOKENS})")
    ap.add_argument("--clusters-file", default=None,
                    help="JSON/YAML file with per-chapter cluster definitions (topic-based "
                         "clustering of definition articles)")
    ap.add_argument("--min-gap", type=int, default=150,
                    help="chars of content after a heading to be considered body, not ToC (default: 150)")
    ap.add_argument("--first-heading", type=int, default=None,
                    help="line number (1-based) of the first real heading; skips ToC detection entirely")
    ap.add_argument("--start-at", type=int, default=None,
                    help="line number (1-based) to start scanning from (skips front matter)")
    ap.add_argument("--dry-run", action="store_true",
                    help="print detected headings and the split plan, write nothing")
    ap.add_argument("--overwrite", action="store_true",
                    help="overwrite existing output files (default: skip existing)")
    args = ap.parse_args(argv)

    try:
        text = Path(args.input).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"error: cannot read {args.input}: {exc}", file=sys.stderr)
        return 1

    clusters = load_clusters(args.clusters_file) if args.clusters_file else None

    lines = text.splitlines()
    start_at = (args.start_at - 1) if args.start_at else 0
    all_headings = find_top_headings(lines[start_at:])
    all_headings = [(ln + start_at, k, t, ai) for ln, k, t, ai in all_headings]

    if args.first_heading is not None:
        body3 = [h for h in all_headings if h[0] >= args.first_heading - 1]
    else:
        body3 = filter_toc(all_headings, lines, args.min_gap)

    # Compute annex context AFTER ToC filtering: CHAPTER/PART headings that
    # follow an ANNEX heading are annex-internal sections (split points, not
    # top-level chapters).
    body: list[tuple[int, str, str, bool]] = []
    annex_secs: dict[int, list[tuple[int, str]]] = {}
    current_annex: int | None = None
    for ln, kind, title, _ai in body3:
        if kind == "annex":
            current_annex = ln
            annex_secs[current_annex] = []
            body.append((ln, kind, title, False))
        else:
            annex_internal = current_annex is not None
            body.append((ln, kind, title, annex_internal))
            if annex_internal:
                annex_secs[current_annex].append((ln, title))

    # Top-level body only: annex-internal sections are split points, not units.
    body = [h for h in body if not h[3]]

    sources = detect_sources(lines)

    if args.dry_run:
        print(f"Detected {len(all_headings)} heading(s); body starts at heading "
              f"{len(all_headings) - len(body) + 1 if body else '-'}.")
        current_source = ""
        for idx, (ln, kind, title, _ai) in enumerate(body):
            end = body[idx + 1][0] if idx + 1 < len(body) else len(lines)
            banner_before = [i for i in sources if i <= ln]
            if banner_before:
                current_source = sources[max(banner_before)]
            section = _trim_trailing_banners(lines[ln:end])
            tokens = estimate_tokens("\n".join(section))
            articles = find_articles(section, 0, len(section))
            split = (
                args.granularity == "article"
                or (args.granularity == "auto" and tokens > args.max_chapter_tokens)
            )
            mode = "SPLIT(L1+L2)" if split else "single"
            print(f"  {ln + 1:6d}  [BODY] {kind:7s} {title}  ({tokens} tok, "
                  f"{len(articles)} art) → {mode}")
        return 0

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    indexes_dir = Path(args.index_dir)

    current_source = ""
    written, skipped = 0, 0
    for idx, (ln, kind, title, _ai) in enumerate(body):
        end = body[idx + 1][0] if idx + 1 < len(body) else len(lines)
        banner_before = [i for i in sources if i <= ln]
        if banner_before:
            current_source = sources[max(banner_before)]
        source_label = current_source or Path(args.input).name

        section = _trim_trailing_banners(lines[ln:end])
        num = idx + 1
        tokens = estimate_tokens("\n".join(section))
        split = (
            args.granularity == "article"
            or (args.granularity == "auto" and tokens > args.max_chapter_tokens)
        )
        annex_sections = [
            (s_ln - ln, s_title) for s_ln, s_title in annex_secs.get(ln, [])
        ]

        if split:
            fnames, any_written = split_articles_chapter(
                num, title, kind, section, source_label,
                out_dir, indexes_dir, args.max_file_tokens, clusters, args.overwrite,
                annex_sections,
            )
            if any_written:
                written += len(fnames)
                print(f"  split ch{num:02d} ({tokens} tok) → {len(fnames)} file(s) + index")
            else:
                skipped += 1
        else:
            fname, did = split_single_chapter(
                num, title, section, source_label, out_dir, args.overwrite,
            )
            if did:
                written += 1
                print(f"  wrote {fname}  ({len(section)} lines, {tokens} tok)")
            else:
                skipped += 1

    print(f"done: {written} file(s) written, {skipped} skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
