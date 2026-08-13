/**
 * site-tools — pi extension for the site-to-skill skill.
 *
 * Registers three custom tools that turn a book-like website into a
 * book-like Markdown corpus, delegating the heavy lifting to the bundled
 * `site2md` Python package:
 *
 *   site_inspect  <url>                → JSON site report + recommended strategy
 *   site2md       <url> <outdir> [opts] → crawl + tidy + assemble corpus
 *   page_extract  <html> <out.md>      → one HTML page → clean Markdown
 *
 * The tools resolve the package root relative to this file, so they keep
 * working wherever pi installs the package (git/npm/local path).
 */

import { execFile } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

import { StringEnum } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

const execFileAsync = promisify(execFile);

const STRATEGIES = ["auto", "source-repo", "search-index", "sitemap", "toc", "bfs"] as const;

export default function siteToolsExtension(pi: ExtensionAPI) {
  const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
  // Prefer the repo-local virtualenv (setup-venv.sh) so crawl4ai/trafilatura
  // live in .venv, never in the system Python. Fall back to an explicit env
  // override, then to the system interpreter.
  const venvPython =
    process.platform === "win32"
      ? resolve(repoRoot, ".venv/Scripts/python.exe")
      : resolve(repoRoot, ".venv/bin/python");
  const python =
    process.env.SITE2MD_PYTHON ??
    (existsSync(venvPython) ? venvPython : "python3");

  async function runCli(args: string[], signal?: AbortSignal, timeoutMs = 900_000): Promise<string> {
    try {
      const { stdout } = await execFileAsync(python, ["-m", "site2md.cli", ...args], {
        cwd: repoRoot,
        env: { ...process.env, PYTHONPATH: repoRoot },
        timeout: timeoutMs,
        maxBuffer: 64 * 1024 * 1024,
        signal,
      });
      return stdout;
    } catch (err) {
      const e = err as { killed?: boolean; signal?: string; stderr?: string; message?: string };
      if (e?.killed || e?.signal === "SIGTERM") {
        throw new Error("site2md cancelled");
      }
      const stderr = (e?.stderr ?? "").slice(-2000);
      if (/No module named ['"]?(crawl4ai|trafilatura|bs4|requests)/.test(stderr)) {
        throw new Error(
          "site2md dependency missing. Install it once with:\n" +
            `  pip install -e "${repoRoot}[crawl]"` +
            (stderr.includes("crawl4ai")
              ? "\n  then: playwright install chromium"
              : "") +
            "\n(stderr: " + stderr.slice(0, 300) + ")"
        );
      }
      throw new Error(`site2md failed: ${stderr || e?.message}`);
    }
  }

  pi.registerTool({
    name: "page_fetch",
    label: "Page Fetch (browser)",
    description:
      "Render a JavaScript-heavy URL in a real browser (crawl4ai/playwright) and return its clean Markdown (nav/header/footer stripped). Use when a page's content is not present in plain HTML: SPAs, client-side rendered docs, lazy-loaded content. Requires the repo-local .venv with the crawl extra (scripts/setup-venv.sh).",
    promptSnippet: "Fetch a dynamic webpage as clean Markdown via a browser",
    promptGuidelines: [
      "Use page_fetch for JS-rendered pages where a plain HTML fetch yields little content.",
    ],
    parameters: Type.Object({
      url: Type.String({ description: "URL to render" }),
      out: Type.Optional(
        Type.String({ description: "Optional output .md path (default: stdout)" }),
      ),
    }),
    async execute(_toolCallId, params, signal) {
      const args = ["browser-md", params.url];
      if (params.out) args.push(params.out);
      const out = await runCli(args, signal);
      return {
        content: [{ type: "text", text: out }],
        details: { tool: "page_fetch", url: params.url },
      };
    },
  });

  pi.registerTool({
    name: "site_inspect",
    label: "Site Inspect",
    description:
      "Probe a website and report its structure: generator/framework detection, discovery of sitemap.xml, search_index.json (bookdown full text), github-repo meta (source repository), dynamic-rendering hints, and a recommended strategy to turn the site into a book-like Markdown corpus. Run this first before site2md.",
    promptSnippet: "Inspect a website to see how to turn it into a book corpus",
    promptGuidelines: [
      "Use site_inspect before site2md to learn the site's structure and let its recommended strategy pick the crawl path.",
      "Use site2md (not manual curl+bs4) to crawl a book-like website into a Markdown corpus.",
    ],
    parameters: Type.Object({
      url: Type.String({ description: "Landing page URL of the book-like site" }),
    }),
    async execute(_toolCallId, params, signal) {
      const out = await runCli(["inspect", params.url], signal);
      return {
        content: [{ type: "text", text: out }],
        details: { tool: "site_inspect", url: params.url },
      };
    },
  });

  pi.registerTool({
    name: "site2md",
    label: "Site to Markdown",
    description:
      "Turn a book-like website into a book-like Markdown corpus at <outdir>/sources/*.md plus metadata.json. Strategies: source-repo (GitHub Rmd/MD sources), search-index (bookdown built-in full text), sitemap, toc (nav links), bfs (bounded crawl). Default auto uses site_inspect's recommendation. The corpus feeds book-to-skill's generation phase.",
    promptSnippet: "Crawl a book-like website into a Markdown corpus",
    promptGuidelines: [
      "Use site2md to crawl a book-like website; then hand the corpus to book-to-skill for skill generation.",
    ],
    parameters: Type.Object({
      url: Type.String({ description: "Landing page URL" }),
      outdir: Type.String({ description: "Output directory (created if missing)" }),
      strategy: Type.Optional(
        StringEnum(STRATEGIES, {
          description: "Crawl strategy; default auto = site_inspect recommendation",
        }),
      ),
      maxPages: Type.Optional(
        Type.Number({ description: "Page cap (default 200)", minimum: 1, maximum: 5000 }),
      ),
      depth: Type.Optional(Type.Number({ description: "BFS link depth (default 2)" })),
      include: Type.Optional(
        Type.String({ description: "Comma-separated fnmatch patterns to keep" }),
      ),
      exclude: Type.Optional(
        Type.String({ description: "Comma-separated fnmatch patterns to drop" }),
      ),
    }),
    async execute(_toolCallId, params, signal) {
      const args = ["crawl", params.url, params.outdir];
      if (params.strategy) args.push("--strategy", params.strategy);
      if (params.maxPages) args.push("--max-pages", String(params.maxPages));
      if (params.depth) args.push("--depth", String(params.depth));
      if (params.include) args.push("--include", params.include);
      if (params.exclude) args.push("--exclude", params.exclude);
      const out = await runCli(args, signal);
      return {
        content: [{ type: "text", text: out }],
        details: { tool: "site2md", url: params.url, outdir: params.outdir },
      };
    },
  });

  pi.registerTool({
    name: "page_extract",
    label: "Page Extract",
    description:
      "Convert one saved HTML file into clean Markdown (strips nav/header/footer/ads/comments; trafilatura then bs4 fallback). For sites where the automatic pipeline needs per-page help.",
    promptSnippet: "Extract clean Markdown from a single HTML file",
    promptGuidelines: [],
    parameters: Type.Object({
      html: Type.String({ description: "Path to the HTML file" }),
      out: Type.String({ description: "Output .md path" }),
    }),
    async execute(_toolCallId, params, signal) {
      const out = await runCli(["page-extract", params.html, params.out], signal);
      return {
        content: [{ type: "text", text: out }],
        details: { tool: "page_extract", html: params.html, out: params.out },
      };
    },
  });
}
