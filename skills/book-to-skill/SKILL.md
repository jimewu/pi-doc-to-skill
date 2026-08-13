---
name: book-to-skill
description: "Converts books, regulations, standards, and document collections (PDF/EPUB/DOCX first converted to Markdown, or Markdown directly) into versioned agent skills. Two modes: reference (verbatim legal/regulatory/standards text, e.g. EU MDR — exact original wording preserved, agents quote it verbatim) and study (distilled learning material, e.g. LPIC textbooks — frameworks, takeaways, glossary). Both modes support updates (new document versions, new guidance, personal insights) via a notes layer. Use when the user wants to turn a document into a reusable expert or study skill for pi or any Agent-Skills-compatible host."
metadata:
  version: 2.0.0
  upstream-version: 1.3.0
  package: pi-doc-to-skill
  spec: docs/skill-generation-spec.md   # generation steps 6-10 live here, shared with site-to-skill
---

<!--
Cross-agent notes (informational; ignored by host agents):
  - Compatible skill roots: pi (~/.agents/skills, ~/.pi/agent/skills,
    .agents/skills, .pi/skills), GitHub Copilot CLI (~/.copilot/skills,
    ~/.agents/skills, .github/skills, .claude/skills, .agents/skills),
    Amp (.agents/skills, ~/.config/agents/skills, ~/.config/amp/skills),
    Claude Code (~/.claude/skills).
  - `allowed-tools` is intentionally omitted to stay agent-neutral. The skill
    needs shell (convert + extract), file read/write, and grep/glob — each host
    will prompt for those on first use.
  - Argument hint: <path-to-document-folder-or-glob>... [skill-name-slug]
-->

# Book-to-Skill Converter

Transform written knowledge into actionable agent skills. Two modes, one pipeline.

## Philosophy

**Reference mode** (regulations, standards, legal text): the original wording *is* the content. Legal text cannot be paraphrased — a changed word is a changed obligation. These skills preserve the exact source text in on-demand chapter files and teach the agent to quote verbatim. Personal work experience is kept in a strictly separate notes layer so it can never be confused with the regulation itself.

**Study mode** (textbooks, exam prep): extract structure, not summaries. A skill is a toolkit of named frameworks, actionable principles, techniques, and anti-patterns — not a book report. The agent applies the author's thinking without re-reading the book.

**Progressive disclosure in both modes**: SKILL.md is a compact map (~4,000 tokens max); chapter files load on demand; notes load on demand. Context stays proportional to the question, not the source.

---

## Modes of Operation

Four paths, route based on what the user asks:

### 1. Full Conversion (Default)
**Trigger:** User provides document/directory/glob paths without special instructions
**Action:** Run Steps 0–9
**Output:** Complete skill with SKILL.md, chapters/, mode-specific supporting files, notes/

### 2. Analyze Only
**Trigger:** User says "analyze", "just extract", or "I want to review before generating"
**Action:** Run Steps 0–3, then produce a structured report (structure map, articles/frameworks found). Stop — do NOT generate skill files.
**Output:** Analysis report for user review

### 3. Generate from Prior Analysis
**Trigger:** User has existing analysis notes or previously ran analyze-only
**Action:** Skip Steps 0–3, use the provided analysis as input, run Steps 4–9
**Output:** Skill files from the provided analysis

### 4. Update / Fold-in (Existing Skill)
**Trigger:** User provides new source paths and indicates they want to update an existing skill (points to an existing skill folder, or the slug already exists in `SKILLS_HOME`)
**Action:** Run Steps 0–2 (validate + convert + extract new files), then the **Update / Fold-in Workflow**
**Output:** Updated skill — new/revised chapters, merged indexes, updated version metadata. Handles: new document versions (old marked `superseded`), new documents (e.g. MDCG guidance into an MDR skill), and personal insights (added to the notes layer).

---

## Skill Locations

This converter runs from any skill host. When locating the helper script or choosing where to write generated skills, prefer these roots in order:

1. pi personal: `~/.agents/skills/` (also loaded by Copilot CLI)
2. pi global: `~/.pi/agent/skills/`
3. GitHub Copilot CLI personal: `~/.copilot/skills/`
4. Claude Code personal: `~/.claude/skills/`
5. Project-local: `.agents/skills/` → `.github/skills/` → `.claude/skills/` → `.pi/skills/`
6. Amp global: `~/.config/agents/skills/` → `~/.config/amp/skills/`

For **generated** skills, pick a destination the user's host agent can discover (Step 5). When more than one valid root exists, ask once and remember for the session.

---

## Step 0 — Out-of-scope check

If no arguments are provided, stop and respond:
> "book-to-skill requires a supported document path, folder, or glob pattern. Usage: `book-to-skill <path-to-document-folder-or-glob>... [skill-name-slug]`"

Throughout the workflow:
- Identify the input paths and the optional skill slug.
- If the last argument is not a file/folder/glob that exists or matches any files, and it looks like a skill slug (lowercase hyphens, alphanumeric), treat it as `SKILL_NAME`.
- Treat all other arguments as `INPUT_PATHS`.
- If any input path is an existing skill directory (contains `SKILL.md` and a `chapters/` sub-folder), or `SKILL_NAME` matches an existing skill slug in `SKILLS_HOME`, flag this run as **Update/Fold-in** (Mode 4).

---

## Step 1 — Validate input

Verify at least one supported file, directory, or glob among `INPUT_PATHS`. Supported inputs:
- **Markdown family (native):** `.md`, `.markdown`, `.txt`, `.rst`, `.adoc`
- **Convertible (via convert-documents-to-markdown, then treated as Markdown):** `.pdf`, `.epub`, `.docx`, `.doc`, `.rtf`, `.odt`, `.ppt`, `.pptx`, `.xls`, `.xlsx`, `.html`

If no supported files are found, stop with a clear error message.

---

## Step 1.5 — Choose mode

Ask the user:

> "What kind of skill do you want to build from these sources?
>
> 1. **Reference** — verbatim knowledge base (regulations, standards, specs, compliance docs). Exact original wording is preserved; the skill quotes it verbatim. Later updates fold in new versions/guidance, and personal interpretations live in a separate notes layer.
> 2. **Study** — distilled learning material (textbooks, exam prep, technical manuals). Frameworks, key takeaways, glossary, cheatsheet. Depth can be quick-reference or deep study."

Store the answer as `MODE` (`reference` | `study`). If the user is unsure, default to `study` (smaller skills, easier to update later into reference if needed).

---

## Step 1.6 — Convert non-Markdown inputs

The skill's mental model is: **the book is Markdown.** Every input becomes Markdown before anything else.

Create a working directory (default `<tempdir>/book_skill_work/`, override with `BOOK_SKILL_WORKDIR`):
```bash
WORKDIR="${BOOK_SKILL_WORKDIR:-$(mktemp -d)}"
mkdir -p "$WORKDIR/sources"
```

For each input that is **not** Markdown-family (`.md/.markdown/.txt/.rst/.adoc`), convert it:

```bash
# General conversion (PDF, EPUB, DOCX, RTF, ODT, PPT, XLS, HTML, ...)
npx -y @firecrawl/anydoc <file> -o "$WORKDIR/sources/<stem>.md"
```

Rules for conversion:
1. `anydoc` detects the format from file content; pass `--format <name>` only when detection cannot work (missing/wrong extension, or stdin).
2. Exit codes: 0 success, 1 conversion failure, 2 usage error. A failure prints one `anydoc: <message>` line to stderr. The CLI never prompts.
3. **Scanned / image-only PDFs**: anydoc exits 1 with `anydoc: unsupported input: ... (Scanned, N pages): OCR is required` on stderr. Do not treat this as a dead end — use the OCR fallback:
   ```bash
   batch-ocr \
       --api $OCR_ENDPOINT <file.pdf>
   ```
   This writes `<file>.md` (plus an `images/` folder) next to the source. Note: the OCR API address is environment-specific — if it fails, ask the user for the current local OCR endpoint.
4. A different stderr message than the OCR case means a genuine conversion failure. For DOCX/EPUB/RTF, if anydoc is unavailable or fails, you may fall back to the native parsers in `scripts/extract.py` (they use `python-docx`/`ebooklib`/`striprtf` when installed) — but PDFs should never fall back to the built-in extractors.
5. If a converted Markdown file is very large (> ~200KB), keep it on disk and work with it via grep/sed/Read offsets (Step 2.6) instead of loading it whole.

After conversion, every input is a Markdown file under `$WORKDIR/sources/`. Markdown-family inputs may be passed through unchanged (copy or reference in place).

**Quality gate — verify the conversion before proceeding.** Garbage in, garbage out: a bad conversion silently corrupts every verbatim quote the skill will ever make. First classify the source, then check accordingly:

```bash
# 0. Source-type classification (regulations/standards): original vs consolidated.
#    Consolidated texts carry revision markers and an amendment history BY DESIGN:
#    ▶M1 … ▶MN markers, "Amended by:" table, page footers like
#    "CELEXID — EN — YYYY.MM.DD — NNN.NNN — N". These are NOT conversion defects.
#    An ORIGINAL text must have none of them — if it does, the conversion leaked
#    layout noise. Detect:
grep -icE "amended by|consolidated|►M[0-9]|▼" "$OUT.md"
```

```bash
# 1. Broken-word artifacts (PDF line-break glue: "manu facturer", "compen sation") —
#    a defect in ANY source type. Reject on any hit.
grep -nE "\\b[a-z]{3,20} [a-z]{3,20}\\b" "$OUT.md" | grep -iE "manu factur|compen sation|qualifi cation|secur ity|intro duct|opera t|technolo gy" | head

# 2. Merged lines (multiple "(N)" items on one line — breaks item-level splitting) —
#    a defect in any source type. Reject on more than a couple of hits.
grep -cE "^\\([0-9]+\\) .*\\([0-9]+\\) " "$OUT.md"

# 3. Layout noise, by source type:
#    - original text: ▼/▶/page footers appearing in the body = defect
#    - consolidated text: ▼/▶/"— EN —" footers are normal; "▼" counts are fine.
#      Page-footers that merged INTO body lines (check #2 catches the worst) are
#      the only real issue; a few standalone "▼B" lines are acceptable (they mark
#      revision boundaries) — note them in Scope & Limits.
grep -cE "▼|▶|^[0-9]{13} — EN —" "$OUT.md"   # interpret per source type
```

**If the checks find real problems** (broken words, merged items, or layout noise in an original text), **do NOT proceed with this conversion.** Re-run with the OCR fallback instead — a verbatim legal/technical skill is only as precise as its source:

```bash
batch-ocr \
    --api $OCR_ENDPOINT <file.pdf>
# writes <file>.md (+ images/) next to the source; use THAT file as the input
```

The OCR endpoint address is environment-specific — if it fails, ask the user for the current local OCR endpoint. Prefer the conversion with zero or fewest defects; record the chosen method in the skill's `sources[].notes`.

**Getting the document when the source site blocks downloads:** EUR-Lex sits behind a WAF and rejects plain curl. Try in order: (1) a national official mirror (e.g. `legislation.gov.uk` for EU regulations — its resources page lists per-version PDFs); (2) `webfetch` (browser-based, may pass the WAF); (3) ask the user to download it manually and provide the file path. For EUR-Lex specifically, be aware of the **original-vs-consolidated trap**: the "EN TXT"/"PDF" download buttons serve the ORIGINAL OJ text; the current consolidated text lives under a separate CELEX id (`CELEXID-YYYYMMDD` style) on the "Consolidated version" tab. If the user wants to discuss the law as currently in force, you need the consolidated version — confirm which one they mean.

---

## Step 2 — Assemble Markdown sources

Run the extraction script on the Markdown sources to produce combined text + metadata:

```bash
SCRIPT_PATH=""
if [ -n "$PI_DOC_TO_SKILL_ROOT" ]; then
  SCRIPT_PATH="$PI_DOC_TO_SKILL_ROOT/scripts/extract.py"
fi
if [ -z "$SCRIPT_PATH" ]; then
for candidate in \
  "$HOME/.agents/skills/book-to-skill/scripts/extract.py" \
  "$HOME/.pi/agent/skills/book-to-skill/scripts/extract.py" \
  "$HOME/.copilot/skills/book-to-skill/scripts/extract.py" \
  "$HOME/.claude/skills/book-to-skill/scripts/extract.py" \
  "$HOME/.pi/agent/git/"*/pi-doc-to-skill/scripts/extract.py \
  "$HOME/.pi/agent/npm/"*/pi-doc-to-skill/scripts/extract.py \
  "$HOME/.pi/agent/npm/node_modules/pi-doc-to-skill/scripts/extract.py" \
  ".agents/skills/book-to-skill/scripts/extract.py" \
  ".github/skills/book-to-skill/scripts/extract.py" \
  ".claude/skills/book-to-skill/scripts/extract.py" \
  ".pi/skills/book-to-skill/scripts/extract.py"
do
  if [ -f "$candidate" ]; then
    SCRIPT_PATH="$candidate"
    break
  fi
done
fi

if [ -z "$SCRIPT_PATH" ]; then
  echo "Could not find scripts/extract.py for book-to-skill" >&2
  echo "Installed as a pi package? Export PI_DOC_TO_SKILL_ROOT=<package-root>." >&2
  exit 1
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  PYTHON_BIN="python"
fi

# All sources are Markdown now — always --mode text
"$PYTHON_BIN" "$SCRIPT_PATH" "$WORKDIR"/sources/*.md --mode text --install-missing ask
```

Set `WORKDIR` to the directory you created in Step 1.6 (pass `BOOK_SKILL_WORKDIR=<that dir>` when running, or copy the markdown files into `<tempdir>/book_skill_work/sources/`).

This creates:
- `<WORKDIR>/full_text.txt` — combined extracted text of all sources with clear source boundaries.
- `<WORKDIR>/metadata.json` — combined size, words, pages, token counts, chapter structure, and per-source details.

**Preflight tip:** run `"$PYTHON_BIN" "$SCRIPT_PATH" --check` to print a per-format report of installed extractors without processing any file.

Read `metadata.json` to inspect the results (token counts are CJK-aware).

---

## Step 2.5 — Pre-flight cost estimate

Read `<WORKDIR>/metadata.json` and present an estimate **before generating**:

```
📖 Sources detected: <total_sources> source(s)
<list each source filename and format from the sources metadata list>
📄 Combined Pages/Sections: ~<N> | Words: ~<N> | Total tokens: ~<N>K

💰 Estimated token cost (Full Conversion / Update):
   Input  (reading + prompts): ~<N>K tokens
   Output (skill files generated/updated):  ~<N>K tokens
   Total:                           ~<N>K tokens

   Cost: multiply the token counts above by your model's current
   input/output per-1M-token rates (quote today's rate; label it an estimate).

   ⏱  Estimated time: ~<N> minutes

📁 Files to be generated/updated:
   SKILL.md + chapter files + supporting files + notes/

➡  Proceed? (or type "analyze only" to preview first)
```

**How to estimate:**
- Input tokens ≈ `estimated_tokens` from metadata × 1.3 (prompt overhead per chapter pass).
- Output tokens:
  - **reference**: SKILL.md ≈ 3,000–4,000; chapters ≈ verbatim source size (≈ `estimated_tokens` minus ToC/noise); notes ≈ 0 at creation.
  - **study**: SKILL.md ≈ 4,000; chapters ≈ chapters × per-chapter budget (Step 7) + 4,500 (glossary + patterns + cheatsheet).
- Cost: report token counts and multiply by the user's current per-1M rates. Do NOT hardcode dollar figures.

Wait for the user to confirm. If they say "analyze only", switch to Mode 2.

---

## Step 2.6 — REPL-style access for large sources (> ~50k tokens)

Treat `full_text.txt` as a queryable corpus, not a single read:

```bash
# Size check before any Read
wc -w "$WORKDIR/full_text.txt"

# Find chapter/article offsets without loading the whole file
grep -n -E "^(#+\s*)?(Chapter|CHAPTER)\s+[0-9IVXLC]+" "$WORKDIR/full_text.txt" | head -60
grep -n -E "^(#+\s*)?Article\s+[0-9]+" "$WORKDIR/full_text.txt" | head -140

# Pull only the section you need
sed -n '<start>,<end>p' "$WORKDIR/full_text.txt"

# Verify a term is actually present before claiming it in SKILL.md
grep -c -i "udi\|vigilance" "$WORKDIR/full_text.txt"

# Targeted Read with offset/limit avoids dumping the full file
```

Use this for Step 3 (structure), Step 7 (chapters), and Step 8 (indexes). On sources under 50k tokens, a single `Read` is fine.

---

## Step 3 — Analyze structure

Read the first 8,000 characters of `full_text.txt` plus the results of `detect_structure` from `metadata.json` to identify:
- **Title** and **author/issuing body** (e.g. "Regulation (EU) 2017/745" — European Parliament and Council)
- **Document version/date** if visible (for a regulation: the OJ citation or "EU 2017/745"; for a textbook: edition/year)
- **Structure**: chapter/article/annex headings, parts, ToC
- Core themes and subject domain

**Version confirmation (regulations, standards, legal texts) — confirm before generating.** Get the version right, because "discussing the law as currently in force" needs the **consolidated** text, not the original:
1. Classify the source: a consolidated text carries an amendment history — a "▶M1 … ▶MN" marker table ("Amended by:"), revision markers (▼/▶) inside the body, and page footers like `CELEXID — EN — YYYY.MM.DD — NNN.NNN — N`. An original text has none of these.
2. If the user wants to discuss the document as in force (a legal/regulatory expert skill), and the source is an ORIGINAL text while a newer consolidated version exists, tell the user and offer to use the consolidated version instead — do not silently build on the original. (EUR-Lex's "TXT/PDF" buttons serve the original; the consolidated text is a separate CELEX id `CELEXID-YYYYMMDD` under the "Consolidated version" tab.)
3. Record the exact version in metadata:
   - original: `version: "EU 2017/745 (OJ L 117, 5.5.2017, p. 1)"`
   - consolidated: `version: "consolidated YYYY.MM.DD (NNN.NNN)"` and list the amendments in `sources[].notes` (e.g. "amendments M1–MN: <regulation refs>; new Article 10a")
4. For non-legal documents (textbooks, manuals) the edition/year is enough — no consolidated/original distinction applies.

Produce a structure map (also useful for the Analyze-Only report):
- **reference**: Chapters/Annexes → article ranges → line offsets (e.g. `Ch02 · Arts 5–22 · lines 1240–3105`)
- **study**: chapters → main frameworks

**If mode is "Analyze Only":** produce the report now and stop (structure map + key findings; for reference mode, a draft Topic Index).

---

## Step 4 — Ask purpose (study mode only)

**reference mode:** skip this step (there is no depth axis — the content is verbatim).

**study mode:** ask:

> "What should this skill help you do?
> 1. Quick reference while working (lean chapters, decision-ready essentials)
> 2. Deep study (worked examples, reasoning, more detail per chapter)
> 3. All of the above"

- Answer is only option 1 → `DEPTH=quick-reference`
- Answer includes 2 or 3 → `DEPTH=study`

(In Modes 2/3, where Step 4 is skipped, default `DEPTH=study`.)

---

## Step 5 — Determine skill name and destination

If `SKILL_NAME` was provided, use it as the skill slug. Otherwise propose two options and let the user choose:
- **By document identity**: from the official title/abbreviation, lowercase hyphens (e.g. `mdr`, `lpic-101`, `iso-13485`)
- **By author-concept** (study mode): `{author-lastname}-{core-concept}` (e.g. `cialdini-influence`)

Default to the document identity for reference mode (users will say "the MDR skill").

Choose the destination root (`SKILLS_HOME`) by the host the user runs:

| Host agent | Personal skill root (probe in order) | Project-local root |
|---|---|---|
| **pi** | `~/.agents/skills` → `~/.pi/agent/skills` | `.agents/skills` → `.pi/skills` |
| **GitHub Copilot CLI** | `~/.copilot/skills` → `~/.agents/skills` | `.github/skills` → `.claude/skills` → `.agents/skills` |
| **Amp** | `~/.agents/skills` → `~/.config/agents/skills` → `~/.config/amp/skills` | `.agents/skills` |
| **Claude Code** | `~/.claude/skills` | `.claude/skills` |

Selection rules:
1. If exactly one of the host's candidate roots exists on disk, use it without asking.
2. If none exist (fresh machine), ask which root to create — present the host-appropriate options.
3. If the user asked for project-local output, prefer the project-local row.
4. If you cannot identify the host, ask: "Which agent are you running this in — pi, GitHub Copilot CLI, Amp, or Claude Code?"

Set `SKILLS_HOME` and check whether `$SKILLS_HOME/<skill_name>/` already exists. If it does, prompt:
1. **Update / Fold-in** (Mode 4) — integrate new files/content
2. **Overwrite** — delete and regenerate from scratch
3. **Rename** — append `-2` or use a different slug

If the user selects **Update / Fold-in**, proceed immediately to the **Update / Fold-in Workflow** in the shared spec (skipping Steps 3, 4, 6, 7, 8, 9).

---

## Steps 6–10 — Generation (shared spec)

Everything after source preparation is **shared with site-to-skill** and lives in a single file, so both skills never drift apart:

> **`<package-root>/docs/skill-generation-spec.md`** — Step 6 (directory structure), Step 7 (chapter generation: verbatim reference / distilled study), Step 8 (supporting files: indexes/glossary/patterns/cheatsheet), Step 8.5 (notes layer), Step 9 (master SKILL.md template), Step 9.5 (scan & verify), Step 10 (cleanup & report), the **Update / Fold-in Workflow**, and the **Quality Rules**.

Locate the package root with the same SCRIPT_PATH probe pattern used above (the repo root is the parent of `scripts/`): after `extract.py` is found, the spec is at `$(dirname "$SCRIPT_PATH")/../docs/skill-generation-spec.md`. Read it before generating any skill files.

---
