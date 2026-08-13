# pi-doc-to-skill

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
pi install <path-to-this-repo>      # 或：pi install git:github.com/you/pi-doc-to-skill
```

網站爬蟲的 Python 依賴（僅**動態/JS 渲染**站需要；靜態站走 stdlib + trafilatura 路徑，零重依賴）：

```bash
pip install -e "<package-root>[crawl]" && playwright install chromium
```

## Custom tools

| Tool | 用途 |
|---|---|
| `site_inspect <url>` | 探查網站：generator 偵測、sitemap / search-index / github-repo 發現、建議策略（JSON） |
| `site2md <url> <outdir> [strategy=…]` | crawl + tidy + 組裝 book-like Markdown corpus（`sources/*.md` + `metadata.json`） |
| `page_extract <html> <out.md>` | 單一 HTML 檔 → 乾淨 Markdown（trafilatura → bs4） |

策略依品質排序：**source-repo**（公開 Rmd/MD 源碼）→ **search-index**（bookdown 全文）→ **sitemap**（版本感知）→ **toc**（導航連結）→ **bfs**（有限深度爬取）。爬蟲同時支援靜態站（requests + trafilatura）與動態站（crawl4ai/playwright，lazy 載入）。

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

## License

MIT — 見 [LICENSE.md](LICENSE.md)。
