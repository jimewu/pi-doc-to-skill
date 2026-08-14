
# Skill Generation Spec (shared)

> **Shared by `book-to-skill` and `site-to-skill`** — the generation phase is identical no matter where the book-like Markdown corpus came from (a converted document or a crawled website). Keep this file the single source of truth for Steps 6–10, the Update/Fold-in Workflow, and the Quality Rules; the two skills only differ in **how they produce the corpus** (Steps 0–5).

## Step 6 — Create skill directory structure

```bash
mkdir -p "$SKILLS_HOME/<skill_name>/chapters"
mkdir -p "$SKILLS_HOME/<skill_name>/indexes"   # L1 sub-chapter indexes (reference)
mkdir -p "$SKILLS_HOME/<skill_name>/notes"      # both modes
# study mode only:
mkdir -p "$SKILLS_HOME/<skill_name>"            # glossary.md, patterns.md, cheatsheet.md live at root
```

The `notes/` directory is created in **both modes** — personal insights attach to any skill. In reference mode the skill uses three-level progressive disclosure:

```
L0  SKILL.md                    — Document Map (Chapter → index file) + Topic Index
L1  indexes/ch<NN>-index.md     — sub-chapter index: articles/items → L2 files
L2  chapters/ch<NN>-art-<NN>.md — actual verbatim content (article/cluster level)
```

---

## Step 7 — Generate chapter files

### reference mode — verbatim chapters

The goal: exact original text, split so no agent ever needs more than one small file for a question.

1. **Split by top-level structure** — one file per Chapter and per Annex (MDR: Chapters I–X + Annexes I–XVII ≈ 27 top-level units).
2. **Whether a chapter gets an L1 index depends on its length** (default: `--granularity auto`):

| Chapter tokens | Structure |
|---|---|
| ≤ 4,000 (`--max-chapter-tokens`) | **single file** `ch<NN>-<slug>.md`, no index layer |
| > 4,000 | **L1+L2**: `indexes/ch<NN>-index.md` + one file per article/cluster under `chapters/` |

   Article-level files target ≤ ~3,000 tokens each (`--max-file-tokens`); an oversized article is split further by its internal numbered items into `ch<NN>-art-<N>-part-<K>.md`. Both thresholds are parameters — adjust for the actual document.
3. **Preferred tool — `scripts/split_reference.py`** (deterministic, avoids transcription errors):
   ```bash
   "$PYTHON_BIN" "$SKILL_CONVERTER_ROOT/scripts/split_reference.py" \
       "$WORKDIR/full_text.txt" -o "$SKILLS_HOME/<skill_name>/chapters" \
       --index-dir "$SKILLS_HOME/<skill_name>/indexes"
   ```
   It detects Chapter/Annex headings (English, CJK, and other styles), skips the ToC heuristically, writes one file per heading (single-file or article-level per the token thresholds), and writes an L1 index for every split chapter. Inspect its output; if the ToC was not skipped correctly, pass `--first-heading <line>` or re-run with `--start-at <line>`. Run with `--dry-run` to preview the split plan first.
4. **Definition-style articles cluster by topic** (e.g. MDR Art 2): group related definitions into one file so no agent loads a 50-definition article wholesale, but definitions are not scattered one-per-file either. Provide the clusters to the splitter via `--clusters-file` (JSON/YAML: per chapter, `file` name + `parts` like `art-2:1-20` / `art-2:21-59`), or split manually. Cluster boundaries come from reading the definitions and grouping by subject (economic operators, device types, clinical evaluation, …).
5. If the splitter is not usable for this document, do it manually: find heading line offsets (Step 2.6), then `sed -n '<start>,<end>p'` each section into its own file.
6. **Guidance documents / standards with numbered sections** (e.g. MDCG guidance: "1. Introduction", "2. Scope", …) do not use CHAPTER/ANNEX headings, so the splitter's top-level detection does not apply. Split them by their numbered section headings instead: locate `N. <Title>` lines (short heading lines; skip table rows that merely start with a number), cut one file per section, and name them `<doc-slug>/sec-<N>-<slug>.md`. The same token-threshold logic applies: a section over ~3,000 tokens with clear sub-headings (e.g. "3.1 Technical characteristics") gets split into `sec-<N>-<M>-<slug>.md` sub-files.
7. **Each added document gets its own L1 index** `<doc-slug>/index.md` (see Step 8), not a row in the primary document's chapter numbering.
6. **Verbatim rule — absolute**: content in chapter files is the source text *as written*. Do not paraphrase, condense, or "clean up" legal wording. Preserve article numbers, paragraph numbering (1., 2., (a), (b)), and headings exactly. The only permitted additions are: the file's own H1 title, the Article/Item Index block at the top, and a one-line `Source:` note.
7. **Split-line rule**: splits never cut inside a paragraph, and every file keeps full citation identity (article number, item numbers intact) — any file can be cited standalone as the legal source.
8. **Per-file header** (single-file chapters):
   ```markdown
   # Chapter II: <Full Title>
   Source: <document name/version>, <Chapter/Annex range>

   > **Article Index**: Articles 5–22
   > - Art 5 — <short topic>  ← one line each, from the chapter's actual headings
   ...
   ```
   Article-level files use `# <Chapter Title> — Art <N>: <title>` with a one-line index block.
9. Skip front matter, ToC, and page furniture (running headers/footers, page numbers) — they are not content.
10. **Source traceability — mandatory for every chapter file (both modes).** The `Source:` line must identify the exact document and its provenance so later updates can be traced:
    - Offline documents: `Source: <Title> (<edition/version>), <filename>`
    - Web sources: `Source: <Title> (<version>), <URL>, accessed <YYYY-MM-DD>` — the access date is **required** for web content because it changes over time.
    - When a skill merges multiple sources, keep each source's files in its own folder (`<doc-slug>/`, see Step 8) so **no single file mixes provenances**; the `Source:` line then names exactly one source per file.

### study mode — distilled chapters

**TOKEN BUDGET by `DEPTH`:**

| | `DEPTH=quick-reference` | `DEPTH=study` |
|---|---|---|
| per-chapter | 800–1,200 tokens | 1,200–2,400 tokens |

Density beats length (Quality Rule #3): never pad to hit a number.

For EACH chapter/section identified in Step 3, read the corresponding section of `full_text.txt` and create `chapters/ch<NN>-<slug>.md`:

```markdown
# Chapter N: <Full Title>
Source: <Title> (<version>), <URL for web sources>, accessed <YYYY-MM-DD>  ← mandatory, one source per file

## Core Idea
<1–2 sentences: the single most important thing this chapter teaches>

## Frameworks Introduced
- **<Framework Name>**: <exact formulation — preserve the author's naming>
  - When to use: <specific situation>
  - How: <steps or criteria>

## Key Concepts
- **<Term>**: <precise definition in 1 sentence>
(5–10 most important terms)

## Mental Models
<2–4 thinking tools. Write as "Use X when Y", "Think of X as Y">

## Anti-patterns
- **<What to avoid>**: <why it fails>

## Code Examples *(if the source has code — omit otherwise)*
```<language>
<key example>
```
- **What it demonstrates**: <one line>

## Worked Example *(DEPTH=study only — omit for quick-reference)*
<!-- Reconstruct one concrete example the author works through. Keep it faithful;
     never copy long raw passages — reconstruct compactly. -->

## Key Takeaways
1. <Actionable insight>
2. <Actionable insight>
3. <Actionable insight>
(3–7 takeaways)

## Connects To
- **Ch N**: <why this chapter relates>
- **<Concept>**: <external concept or standard>
```

**`DEPTH=study` earns its budget with content, not a bigger number**: reproduce one worked example (`## Worked Example`), expand each framework's "How" into explicit steps, add a "Why it works / failure mode" note to the top 1–2 frameworks. If a chapter genuinely has no material, let it land below the floor rather than padding.

---

## Step 8 — Generate supporting files

### reference mode

1. **`notes/` initialization** — create the notes directory (Step 6) and a `notes/README.md` explaining the naming convention (see Notes Layer below).
2. **L1 indexes (`indexes/`)** — generated by the splitter for every split chapter (Step 7). The splitter writes the **Articles** table (file → article, with titles) and an empty **Topics** table. **Fill the Topics table — this is a mandatory step.**
   - For every `indexes/ch<NN>-index.md`, fill `## Topics` with a `| Topic | Articles → Files |` mapping: group the chapter's articles by subject, and link each topic to the exact article files.
   - This is the sub-topic layer that makes the L1 index useful: a reader asking "Class IIa clinical investigations" must be able to go from the Topic row straight to `ch06-art-62`, `ch06-art-68`, … **without loading the whole chapter**.
   - How: read the article titles in the index's Articles table (they carry the subjects); skim an article file's first lines when the title is not enough. Produce ~5–15 topics per chapter (more for long chapters), each mapping to the specific articles that cover it.
   - **Topic wording must match how a practitioner would ask, not just the statutory titles.** Article titles are formal ("Art 62 — General requirements regarding clinical investigations conducted to demonstrate conformity"); real questions use domain vocabulary ("Class IIa clinical investigations", "post-market investigations", "legacy certificates", "transitional provisions", "UDI database"). When grouping, add the practical alias into the Topic cell so a plain-language query lands on the right articles. Use your knowledge of the domain to spot the groupings the user will actually ask about.
   - Example (Chapter VI, clinical evaluation & investigations):
     ```
     | Clinical evaluation (incl. plan, equivalence) | [Art 61](ch06-art-61.md) |
     | Clinical investigations — general requirements | [Art 62](ch06-art-62.md), [Art 70](ch06-art-70.md), [Art 71](ch06-art-71.md) |
     | Vulnerable subjects (minors, pregnant women, emergency) | [Art 64](ch06-art-64.md), [Art 65](ch06-art-65.md), [Art 66](ch06-art-66.md), [Art 68](ch06-art-68.md) |
     | Safety reporting & end of investigation | [Art 75](ch06-art-75.md), [Art 80](ch06-art-80.md), [Art 82](ch06-art-82.md) |
     ```
   - Annexes: same treatment — `indexes/ch<NN>-index.md` for split annexes gets a Topics table mapping the annex's internal sections/items to files.
   - **Added documents (`<doc-slug>/`)**: build `<doc-slug>/index.md` as their L1 — a section→file table (with a one-line description per section) plus a **cross-reference table back to the primary document's provisions** (e.g. MDCG 2020-5 index maps Art 61(3)–(5) and Annex XIV Part A to its Sections 3–4). Fill it even if the document is short; it is what lets the agent navigate the second source without loading it whole.
3. **Article/Item Index** — prepended by the splitter (Step 7). Verify each file's index block lists the right article/item numbers.
4. **Cross-reference map** — from the source text, note articles that reference other articles/annexes (e.g. "Art 10 refers to Annexes I and IX"). Keep it in the SKILL.md Topic Index or as a compact `cross-refs.md` if large. This is what lets the agent follow the regulation's internal logic.

### study mode

- **glossary.md** — every significant term, alphabetically sorted: `**Term** — definition (Ch N)`; max 1,500 tokens.
- **patterns.md** — concrete techniques/patterns: `## Pattern Name` / **When to use** / **How** / **Trade-offs**; max 2,000 tokens.
- **cheatsheet.md** — the decision layer: decision rules ("When X, do Y, because Z"), decision trees, trade-off matrices, thresholds & defaults, tells & smells. Max 1,200 tokens. Every line should help the reader *decide* something.

---

## Step 8.5 — Notes layer (both modes)

Personal insights live in `<skill>/notes/` — **never** inside chapter files. This separation is the contract that keeps original text trustworthy.

**Filename convention** (this is what agents search for — document it in `notes/README.md`):
```
<target>-<YYYY-MM-DD>-<slug>.md
```
- `<target>` — normalized reference to what the note annotates:
  - `art-<N>` — an article (e.g. `art-27`)
  - `ch<NN>` / `chapter-<roman>` — a chapter
  - `annex-<roman>` — an annex
  - `<doc-ref>` — another document (e.g. `mdcg-2021-24`, `iso-13485`)
  - `general` — a note not tied to a specific provision
- `<slug>` — short descriptive text, lowercase hyphens.

Examples: `art-27-2026-08-06-udi-rule-note.md`, `mdcg-2021-24-2026-08-06-annex-x-note.md`, `general-2026-08-06-import-classes-note.md`.

**Note file structure:**
```markdown
---
target: art-27
date: 2026-08-06
author: <user>
applies-to: Article 27(1)-(4)   # precise scope this insight covers
applies-to-version: consolidated 01.01.2026   # document version the insight was written against (omit for timeless insights)
tags: [udi, labelling]
---

<the personal insight — your interpretation, work experience, internal practice.
 NOT the regulation text; if you quote the text, quote it and mark it clearly.>
```

**Version binding (`applies-to-version`):** an insight is written against a specific version of the document. When the skill is updated to a newer version (e.g. a new consolidated text), a note may become stale — the old version's Article 120 deadlines, for instance, may have changed. On every update:
1. Read each existing note's `applies-to-version`.
2. If a note targets a provision that the new version changed, flag it in the update report and ask the user whether to keep, update, or archive the note (move to `notes/archive/`).
3. New notes default to the current source version.

**Agent behavior rule (write this into the generated SKILL.md):**
> When asked about any article, chapter, annex, or referenced document, FIRST check the notes layer: `ls <skill>/notes/` and `ls <skill>/notes/*<target>*` (e.g. `notes/*art-27*`). If a matching note exists, read it and — when relevant — present it clearly labeled as **Personal note / interpretation** (with date/author), never blended into the verbatim text. If the note's `applies-to-version` differs from the skill's source version, say so when citing it.

**Adding notes:** when the user dictates a personal insight during a session, create the note file on the spot (date = today, `applies-to-version` = the current source version), and update the Notes Index in SKILL.md (Step 9).

---

## Step 9 — Generate the master SKILL.md

**CRITICAL: keep the SKILL.md body under ~4,000 tokens.** Compaction truncates from the END — put the most important content FIRST.

### Frontmatter (both modes)

```yaml
---
name: <skill_name>
description: "Use when an agent must <what the user asks that triggers this skill>. <1–2 clauses of scope, no feature inventory>"
metadata:
  version: 1.0.0                       # this skill's own version; bump per update
  book-to-skill-version: 2.0.0        # pi-doc-to-skill package version used to create/update it
  mode: reference                      # or study
  sources:
    - name: "Regulation (EU) 2017/745 (MDR)"
      kind: regulation                 # regulation | standard | textbook | guidance | other
      version: "EU 2017/745"           # document version; if none, use date
      date: 2017-05-05
      file: mdr.pdf
      status: current                  # current | superseded
      notes: ""                        # optional free text
---
```

**`description` is a trigger, not a table of contents** — it decides when the agent loads the skill, so it must answer only "when should I use this?": start with `Use when an agent must …`, name the user-visible goal, optionally 1–2 clauses of scope. **Hard limit ≤ 1024 characters** (Agent Skills standard; pi warns beyond it). Do NOT list the covered features, options, sources, versions, or local-testing details — that content belongs in the body; sources/versions go in `metadata.sources`, not in `description`.

Other rules: every source needs `version` **or** `date`; a `superseded` source stays listed so old references still resolve, but the SKILL.md map points to the current one.

### reference mode body

```markdown
<!-- argument-hint: [article number, chapter, annex, or topic] -->

# <Full Title>
**Issuer**: <body> | **Version**: <doc version> | **Updated**: <YYYY-MM-DD> | **Skill version**: 1.0.0

## How to Use This Skill

- **Ask about an article** — e.g. "what does Art 27 say?" → I use the Document Map to find its chapter, read the L1 index if present, then the exact article file, and quote the text **verbatim**.
- **Ask about a topic** — I use the Topic Index to find the articles, then navigate (map → index → file) and answer from the exact text.
- **Ask about a chapter/annex** — short chapters load directly; split chapters load `indexes/ch<NN>-index.md` first, use its **Topics** table to find the relevant article(s), then load only those article files. I never load a whole long chapter at once.
- **Personal notes** — I always check `notes/` for matching insights and present them clearly labeled.

**IMPORTANT — verbatim rule**: article text is quoted exactly as written in the source. I do not paraphrase or "summarize" legal wording. Personal interpretations come only from the notes layer and are always labeled as such.

---

## Source Hierarchy *(only when more than one source)*

<!-- State the rank of each source and the reconciliation rule. Example: -->

This skill contains **<N> sources of different ranks — they are not interchangeable and neither overrides the other**:

- **<Primary> — <binding|non-binding>**: <one line: what governs; verbatim rule applies if binding>. Files: `<primary docs/>`.
- **<Secondary> — <binding|non-binding>**: <one line: what it adds; it explains how to apply the primary text but is never a substitute>. Files: `<secondary slug>/`.

Questions covering both must draw on **both**: quote the <primary> provision verbatim first, then the <secondary> for the practical detail. **Reconciliation rule**: if the two disagree or the meaning is unclear, do not pick one side — create a user note (target = the primary provision, `applies-to` = the secondary's section) and cite it as personal interpretation.

---

## Document Map

<!-- One map per source. Primary document first; each added document gets its own
     section pointing at its L1 index (see Update Workflow, source-addition pattern). -->
| Chapter | Structure | Articles | Files |
|---------|-----------|----------|-------|
| ch01 | Chapter I — Scope and definitions | 1–4 | [ch01](chapters/ch01-*.md) *(single file)* |
| ch02 | Chapter II — ... | 5–22 | [index](indexes/ch02-index.md) → article files in `chapters/` |
| ... |
| ch27 | Annex I — ... | — | [ch27](chapters/ch27-annex-*.md) |

> Long chapters (> ~4,000 tokens) are split: the Document Map points to `indexes/ch<NN>-index.md` (L1), which lists the article-level files (L2) under `chapters/`. Short chapters are single files and need no index.

## Topic Index
<!-- Alphabetical. Topic → articles → navigation path. -->
- **<Topic>** → Arts <n>–<m> → [ch<NN>](indexes/ch<NN>-index.md) → [art-<n>](chapters/ch<NN>-art-<n>-*.md)
- **<Topic>** → Arts <n> → ch<NN> *(single file)*

## Cross-references
<!-- Key article→article/annex references the agent should know without searching. -->
- Art 10 → Annexes I, IX

## Notes Index
<!-- Every file in notes/ and what it annotates. Regenerate on every update. -->
| Note | Target | Date |
|------|--------|------|
| [art-27-2026-08-06-udi-rule-note.md](notes/...) | Art 27 | 2026-08-06 |

---

## Scope & Limits
This skill covers <documents, versions>. Superseded versions: <list>. For topics beyond these documents, ask the agent directly.
```

### study mode body

Use the upstream template: `## How to Use This Skill`, `## Core Frameworks & Mental Models` (~2,000 tokens, "Use X when Y"), `## Chapter Index` (table with links), `## Topic Index`, `## Supporting Files` (glossary/patterns/cheatsheet), `## Notes Index` (same as reference), `## Scope & Limits`. Frontmatter as above.

---

## Step 9.5 — Scan and verify the generated skill

Before reporting success, run the advisory security scan:

```bash
SKILL_CONVERTER_ROOT="$(cd "$(dirname "$SCRIPT_PATH")/.." && pwd)"
"$PYTHON_BIN" "$SKILL_CONVERTER_ROOT/tools/scan_generated_skill.py" "$SKILLS_HOME/<skill_name>"
```

Then run the **structural verification** — a heading-detection slip silently shifts every chapter number, and a dead link breaks the navigation contract. All three checks are mandatory:

```bash
cd "$SKILLS_HOME/<skill_name>"

# 1. Chapter mapping sanity: every Document Map row must resolve to a real file.
#    A heading misread (e.g. "PARTS AND COMPONENTS" → "Part S") shifts ALL
#    subsequent chapter numbers — spot-check the map against the filesystem.
for f in indexes/*.md chapters/*.md; do test -f "$f" || echo "MISSING: $f"; done

# 2. Link integrity: every Topics / Document Map link target exists.
grep -rhoE '\(([a-z0-9_./-]+\.md)\)' SKILL.md indexes/ | tr -d '()' | sort -u | \
  while read -r target; do test -f "$target" || echo "DEAD LINK: $target"; done

# 3. Verbatim spot-check: diff 2–3 articles (including one the user cares about)
#    against the source. Extract the source span and the chapter-file body and
#    compare, ignoring blank lines.
#    e.g. for Art 27: diff <(sed -n '/^## Article 27$/,/^## Article 28$/p' _source.md | grep -v '^$') \
#                    <(sed -n '/^---$/,$p' chapters/ch03-art-27.md | sed '1d' | grep -v '^$')
```

- **Any MISSING / DEAD LINK / diff mismatch → fix before proceeding.** If a heading was misdetected, re-run the splitter (fix the source or pass `--first-heading`), regenerate the affected indexes/SKILL.md, and re-verify. Do not report success with broken structure.
- If the security scanner exits non-zero, stop and ask a human to review its findings. Do not silently rewrite generated files.

---

## Step 10 — Cleanup and report

```bash
"$PYTHON_BIN" - <<'PY'
import os, shutil, tempfile
from pathlib import Path
shutil.rmtree(
    os.environ.get("BOOK_SKILL_WORKDIR", Path(tempfile.gettempdir()) / "book_skill_work"),
    ignore_errors=True,
)
PY
```

Then report to the user:

```
✅ Skill created/updated: $SKILLS_HOME/<skill_name>/

📄 Source: <Title> (<version>) — <issuer/author>
🔖 Mode: reference|study | Skill version: <version>
📁 Structure: <N> chapters/annexes | <N> notes

Files:
  SKILL.md         — document map + indexes        (~X tokens)
  chapters/        — <N> on-demand files           (~X tokens total)
  notes/           — personal insights layer       (<N> notes)
  [study] glossary.md · patterns.md · cheatsheet.md

💡 Tip: check your agent's session cost/usage command for actual token usage.

Usage:
  Ask for <skill_name> about <article/topic>  → expert answer from exact text
  Ask for <skill_name> ch<N>                  → load a specific chapter
  Ask to add a note to <skill_name>           → personal insight, stored in notes/
```

---

## Update / Fold-in Workflow

When updating an existing skill at `$SKILLS_HOME/<skill_name>/`:

### 1. Read the Existing Skill
- Read `SKILL.md` frontmatter: `version`, `book-to-skill-version`, `mode`, `sources` (names, versions, statuses).
- Parse the Document Map / Chapter Index, Topic Index, Notes Index.
- List `chapters/` and `indexes/` to find the highest chapter number and current numbering scheme.
- List `notes/` to see existing notes, their targets, and each note's `applies-to-version` (version-binding check per Step 8.5).

### 2. Classify the Update

Decide what kind of change this is, then apply the matching pattern:

- **Source update** (a NEW VERSION of an existing source, e.g. a new consolidated MDR revision): the new document supersedes an existing source. Convert + extract (Steps 1.6–2), **confirm the version intent first (Step 3 version confirmation: original vs consolidated)**, generate its chapters, and mark the old source `status: superseded` in frontmatter. Keep old chapters (or move them under a `chapters/legacy/` folder if they clash with new numbering); the Document Map marks them `(superseded)`. Then run the **notes version-binding check** (Step 8.5): flag notes whose `applies-to-version` is superseded and ask the user how to handle each (keep / update / archive).
- **Source addition — same-family document** (a related document of the SAME rank, e.g. a second standard, a second textbook): append chapters after the highest number (e.g. existing stops at `ch27` → new files `ch28-*`), merge Topic Index entries (append new chapter links to existing topics).
- **Source addition — different-rank document (the common regulatory case)**: a related document of a DIFFERENT rank (e.g. MDCG guidance into an MDR skill, implementing regulation into a directive skill, best-practice annex into a standard skill). Do **NOT** append to the primary document's chapter numbering — mixing ranks in one `ch<N>` sequence misleads navigation (ch28 would look like an MDR chapter). Instead:
  1. **Separate directory** for the added document: `<skill>/<doc-slug>/` (e.g. `mdcg-2020-5/`), with its own per-section files and its own **L1 index** (`<doc-slug>/index.md`: sections → files + a cross-reference table to the primary document's provisions).
  2. **Source hierarchy** in SKILL.md (see Step 9): state each source's rank (regulation/standard = binding; guidance/best-practice = non-binding) and the discussion order; sources never override each other.
  3. **Bidirectional cross-references**: link the primary document's relevant Topic Index rows / chapter Topics tables to the added document's sections, and the added document's index cross-reference table back to the primary provisions.
  4. **Reconciliation rule**: where the two sources' wording is unclear or conflicts, do not pick one — create a user note (target = primary provision, `applies-to` = the added document's section) so the ambiguity is recorded as personal interpretation (Step 8.5).
- **Source replacement (supersede — the common tool-evolution case)**: a NEW source that replaces part of an existing one (e.g. officedown::rdocx_document replacing rmarkdown::word_document for docx work). Treat it as a source addition (separate `<doc-slug>/` folder + own L1 index + own files) PLUS:
  1. **Mark the superseded files/rows** `(superseded)` in the Document Map / Topic Index instead of silently deleting — old references must still resolve. If the replacement is total and the user confirms, the superseded files may be removed; record the deletion in the update report.
  2. **Re-point the Topic Index**: rows that previously led to the superseded content now lead to the replacement folder first, with a `(superseded → see <doc-slug>)` note on the old row.
  3. **One source per file**: the replacement folder's files carry only its own `Source:` line (URL + access date for web sources); never merge two provenances in one file.
- **Experience distillation (user practice → a standalone source)**: the user's own working practice, generalized from real work artifacts (case files, projects) into an original methodology source. Unlike the patterns above, the content is **newly written** — a generalization of how the user actually works, not a transcription of any document. Follow these steps:
  1. **Confirm the extraction aspect FIRST (mandatory — ask the user).** A case can yield multiple aspects, e.g. for a CER document: aspect A "how the Rmd project is organized" (hierarchical children, variable tables) vs. aspect B "how a CER is written" (section structure, regulatory mapping). List the candidate aspects you see in the material and let the user pick; **one aspect = one source** — never mix aspects in one folder. Do not guess the aspect yourself.
  2. **Confidentiality boundary**: the user's artifacts may be under NDA. Read only *structure / methods / naming conventions* — never copy case content (device names, data, numbers, paths, client info) into the skill. The distilled source must be expressed in generic language and stay valid for other projects.
  3. **Authorize before embedding personal code**: helper functions/templates the user wrote (e.g. `colratio`, `theme_ms`) are included only with the user's explicit consent, marked as the recommended defaults.
  4. **Write it as its own folder** `<doc-slug>/` (e.g. `workflow/`) with its own L1 index, following Step 7's per-file rules; `Source:` line reads `user's working practice (distilled <YYYY-MM-DD>) — original content, not from a public document or case file`. In frontmatter use `kind: practice`, `version: user's working practice (distilled <date>)`.
  5. **Integrate like any source**: add to `metadata.sources`, point Topic Index rows at it, and — if the practice changes how agents should behave (e.g. "large documents MUST use hierarchical authoring") — state that rule in the SKILL.md body (How to Use / decision layer), not only in the folder.
- **Personal insight**: create the note file (Step 8.5) and add it to the Notes Index. No chapter changes.

### 3. Merge and Regenerate
- Chapters: follow Step 7 for new/revised files.
- Supporting files: reference mode → regenerate L1 indexes, Article Indexes, Cross-references, Notes Index. Study mode → merge glossary (alphabetize, append new chapter refs to existing terms), patterns, cheatsheet.
- Master SKILL.md: regenerate per Step 9, folding new content into the maps/indexes and keeping the body ≤ ~4,000 tokens.

### 4. Bump the version
| Change | Bump |
|---|---|
| Source update (new version supersedes old) | minor |
| Source addition (new document folded in) | minor |
| Personal insight / note added | patch |
| Full rebuild / new book | major (or start at 1.0.0) |

Update `metadata.version`, `sources[].status`, the `Updated` date, and the Notes Index. Also bump `book-to-skill-version` if the converter itself changed.

### 5. Scan, Cleanup, Report
Run Step 9.5, then Step 10 with a custom update report: new chapters, superseded sources, merged index entries, notes added.

---

## Quality Rules

1. **Progressive disclosure** — SKILL.md ≤ ~4,000 tokens (map + rules). In reference mode, long chapters (> ~4,000 tokens) are split further: L1 `indexes/ch<NN>-index.md` (Articles table **+ Topics table** mapping sub-topics → article files) → L2 article files. Never load a whole long chapter at once — navigate map → index Topics → article file.
2. **Verbatim rule (reference)** — chapter files contain the exact source text; never paraphrase, condense, or rewrite legal/standard wording. "A changed word is a changed obligation."
3. **Original vs notes separation** — chapters/ holds only source text; notes/ holds only personal insight. Never mix them.
4. **Notes discovery** — when answering about any article/chapter/annex/document, always check `notes/` for matching files (`notes/*<target>*`) first; label personal insights clearly (date + author) when presenting.
5. **Extract structure, not summaries (study)** — named frameworks, exact formulations, anti-patterns; not chapter recaps.
6. **Preserve the author's precision (study)** — "The 5 Whys" ≠ "ask why multiple times"; keep exact naming.
7. **Density over completeness (study)** — a 1,000-token summary beats a 10,000-token excerpt; never pad to hit a budget.
8. **Practitioner voice (study)** — write "Use X when Y", not "The book explains X".
9. **Version discipline** — every generated skill carries versioned metadata (own version, book-to-skill version, per-source version/date, status); every update bumps it and updates indexes (L1, topic, notes).
10. **Topic index is critical** — it's how the agent navigates to the right chapter file.
11. **Never copy raw book text (study)** — synthesize, summarize, extract signal. (Inverted by rule 2 for reference mode.)
12. **Copyright care** — generated skills of third-party copyrighted works (incl. standards) are for personal/internal use only; do not redistribute. Public legal texts are fine to use freely.
13. **Source traceability** — every chapter file carries a `Source:` line naming exactly ONE source: title/version and, for web sources, the URL + access date. Multi-source skills keep each source in its own folder (`<doc-slug>/`) so a file never mixes provenances.
