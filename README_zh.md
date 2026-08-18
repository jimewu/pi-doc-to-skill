# pi-doc-to-skill

> **English version**: [README.md](README.md)

把**文件**（PDF/EPUB/DOCX/Markdown…）與**像一本書的網站**（文檔站、線上書籍、課程站）轉成可重複使用的 agent skill — 以單一自洽的 [pi](https://github.com/earendil-works/pi-coding-agent) package 形式提供。

```
book-to-skill:  文件（PDF/EPUB/DOCX/…）→ 轉換 → corpus ┐
site-to-skill:  網站（URL）→ inspect → crawl+tidy → corpus ─┤
                                                          ▼
                          docs/skill-generation-spec.md（共用）
                                                          ▼
                                            版本化的 agent skill
```

## 內容

| 元件 | 功能 |
|---|---|
| `skills/book-to-skill` | 文件 → reference（逐字）/ study（摘要）skill |
| `skills/site-to-skill` | 書狀**網站** → skill（新增） |
| `extensions/site-tools.ts` | site-to-skill 背後的 pi custom tools |
| `site2md/` | Python crawler/tidy 套件（inspect + crawl + extract + assemble） |
| `book_to_skill/`、`scripts/`、`tools/` | 共用核心：抽取、reference 切分、skill 掃描/驗證 |
| `docs/skill-generation-spec.md` | **共用**生成規範（Steps 6–10）— 單一檔案、兩 skill 共用 |

兩個 skill 在「產生 corpus 之後」的一切全部共用：生成規範、`scripts/`、`tools/`、notes 層、品質規則。差異只在如何取得 book-like Markdown。

## 安裝

```bash
pi install git:github.com/jimewu/pi-doc-to-skill      # 或讓 pi 指向本 repo 的 local checkout
```

Python 依賴放在 **repo 本機 virtualenv**（`.venv/`，已 gitignore），crawl4ai/trafilatura 不會碰系統 Python。一次性設定：

```bash
bash scripts/setup-venv.sh    # .venv + crawl extra + playwright chromium
```

extension tools 會自動使用 `.venv/bin/python`（可用 `SITE2MD_PYTHON` 覆蓋）。靜態站完全不需要 virtualenv — 只有動態（JS 渲染）站需要。

## Custom tools

| Tool | 用途 |
|---|---|
| `site_inspect <url>` | 探查網站：generator 偵測、sitemap / search-index / github-repo 發現、建議策略（JSON） |
| `site2md <url> <outdir> [strategy=…]` | crawl + tidy + 組裝 book-like Markdown corpus（`sources/*.md` + `metadata.json`） |
| `page_fetch <url> [out]` | 用瀏覽器渲染單一 **JS 重度** URL（crawl4ai/playwright）→ 乾淨 Markdown。獨立可復用 |
| `page_extract <html> <out.md>` | 單一 HTML 檔 → 乾淨 Markdown（trafilatura → bs4） |

策略依品質排序：**source-repo**（公開 Rmd/MD 源碼）→ **search-index**（bookdown 全文）→ **sitemap**（版本感知）→ **toc**（導航連結）→ **bfs**（有限深度爬取）。爬蟲同時支援靜態站（requests + trafilatura）與動態站（`page_fetch`/crawl4ai/playwright）。

## 快速上手

```bash
# 1. 探查書狀網站
site_inspect https://pkg.yihui.org/rmarkdown-book/
# → generator: bookdown, github_repo: rstudio/rmarkdown-book, strategy: source-repo

# 2. 建立 corpus
site2md https://pkg.yihui.org/rmarkdown-book/ /tmp/book --strategy source-repo
# → /tmp/book/sources/*.md + metadata.json

# 3. 交給 book-to-skill（reference/study）— 直接問 agent，例如：
#    "把 /tmp/book 轉成 study skill，命名 rmarkdown-guide"
```

## 開發

```bash
pip install pytest beautifulsoup4
pytest tests/ -q          # 315 tests，網路已 mock
ruff check --select E9,F book_to_skill/ site2md/ scripts/ tests/ tools/
```

## 安全性

見 [SECURITY-NOTICE.md](SECURITY-NOTICE.md) —— 已知存在**惡意冒名的 upstream `book-to-skill` 重傳版**（`Leutenegger/book-to-skill`，含竊取加密錢包資料行為）。請只從本 fork 官方來源（`git:github.com/jimewu/pi-doc-to-skill`）或 upstream 專案（`virgiliojr94/book-to-skill`）安裝。

## 與 upstream（book-to-skill）的關係

本 repo 是 [`virgiliojr94/book-to-skill`](https://github.com/virgiliojr94/book-to-skill) 的 **fork**（fork 點 ≈ upstream commit `b4b3733`，2026-08-06，v1.4.0 前一版）。fork 之後路線差異已大到兩者無法直接互換。**以 local 為準** —— fork 被重新初始化為全新 git 歷史（與 `origin/master` 無共同祖先），因此在未經審慎評估前不會向 `origin` push。

### 與 baseline 的路線差異

| 面向 | 本 fork（pi-doc-to-skill） | Baseline（book-to-skill） |
|---|---|---|
| 封裝 | 自洽的 **pi package**（`pi install`）：2 skills + custom-tools extension | 獨立 skill，供 Copilot CLI / Amp / Claude Code 使用 |
| 文件轉換 | skill 層使用 **anydoc**（Firecrawl）+ 掃描 PDF 的 **OCR fallback**（batch-ocr）；品質 gate 拒絕有缺漏的轉換結果 | 內建抽取器（pdftotext / pypdf / pdfminer / Docling） |
| 來源 | 文件**以及書狀網站**（site2md 爬蟲 + `site_inspect` / `site2md` / `page_fetch` / `page_extract` tools） | 僅文件 |
| skill 模式 | 明確的 **reference（逐字）/ study（摘要）** 分流；兩模式都有 notes 層；法規/標準文本逐字切分（`scripts/split_reference.py`，本 fork 獨有） | 以 study 為主；text/technical 書籍類型 + DEPTH 軸 |
| 生成規範 | 單一共用 `docs/skill-generation-spec.md`（Steps 6–10、品質規則），兩 skill 共用 | 全部寫在 SKILL.md |
| Python 環境 | repo 本機 `.venv`（`scripts/setup-venv.sh`）；pyproject 提供 `crawl` extra | 系統 Python，執行時提示安裝選用套件 |

分歧的設計理由見 `CHANGELOG.md`。

## License

MIT — 見 [LICENSE.md](LICENSE.md)。
