#!/usr/bin/env bash
# Create the repo-local virtualenv (.venv) with all crawl dependencies:
# crawl4ai (playwright + chromium), trafilatura, beautifulsoup4, requests.
#
# The pi extension tools prefer .venv/bin/python automatically; you only need
# to run this once per machine. .venv/ is git-ignored.
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python3}"
echo "==> creating .venv with $PYTHON"
"$PYTHON" -m venv .venv
.venv/bin/pip install --upgrade pip

echo "==> installing package (editable) + crawl extra"
.venv/bin/pip install -e ".[crawl]"

echo "==> installing playwright chromium (for crawl4ai)"
.venv/bin/playwright install chromium

echo "==> done. Tools will use .venv/bin/python automatically."
echo "    Sanity check: .venv/bin/python -m site2md.cli inspect <url>"
