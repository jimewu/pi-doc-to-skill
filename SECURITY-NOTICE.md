# Security notice — malicious `book-to-skill` re-uploads

**Date:** 2026-08-17 (updated for this fork)

This project is a fork of the open-source
[`book-to-skill`](https://github.com/virgiliojr94/book-to-skill) converter.
Make sure you install it — or any `book-to-skill`-derived tool — **only from the
source you intended**. The project is popular enough that impostors exist.

## Official sources

| Project | Repository |
|---|---|
| Upstream `book-to-skill` (original) | `https://github.com/virgiliojr94/book-to-skill` |
| This fork (`pi-doc-to-skill`) | `https://github.com/jimewu/pi-doc-to-skill` |

Install this fork with:

```bash
pi install git:github.com/jimewu/pi-doc-to-skill
```

## Known malicious re-upload of the upstream project

A separate repository at `Leutenegger/book-to-skill` is **not affiliated with,
maintained by, or endorsed by** the upstream project or this fork. Independent
review of its published source found behavior not present in the official
project, including:

- disabling TLS certificate verification;
- sending host/system/repository metadata to an external Cloudflare Worker;
- enumerating local browser-extension storage associated with cryptocurrency
  wallets and Ledger application data;
- archiving and uploading collected local data to an external endpoint on macOS;
- shipping a Windows ZIP/EXE payload that the modified CLI can automatically
  extract and launch.

**Do not install or run it.** If you already executed it on a machine containing
wallet software, treat the relevant local wallet data as potentially
compromised and follow the wallet provider's incident-recovery guidance from a
clean device.

Community report and upstream-maintainer confirmation:
https://github.com/virgiliojr94/book-to-skill/issues/174

## Verify before installing

- Install from the URLs above only — or from a repository you have explicitly
  reviewed and trust.
- After cloning, confirm the remote:
  ```bash
  git -C <repo> remote -v    # must print the intended official URL
  git -C <repo> log -1 --oneline
  ```
- The official projects:
  - do **not** disable TLS verification;
  - do **not** enumerate wallets, browser extensions, or wallet data;
  - do **not** upload collected local data anywhere;
  - do **not** ship or auto-extract executable payloads (ZIP/EXE).

## What this package does (and does not) do

- Runs conversion/extraction/crawling locally; generated skills stay on your
  machine unless you publish them yourself.
- The only network activity is the one you start: fetching crawl targets
  (`site2md`), on-demand conversion tools (`npx @firecrawl/anydoc`), and
  package installs (`pip` / `pi install`).
- No telemetry, no analytics, no wallet or credential access.

If you find a suspicious copy of this project, please report it to the relevant
service provider (and open an issue on this repository).