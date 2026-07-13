#!/usr/bin/env bash
# X bookmarks source: snapshot via vendored xtap, append new ones to
# Sources/x-bookmarks/. No commit here; the orchestrator commits.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export XTAP_HOME="${XTAP_HOME:-$HOME/.xtap}"
mkdir -p "$XTAP_HOME"

# shellcheck disable=SC1091
source "$ROOT/.venv/bin/activate"
BROWSER="$($ROOT/.venv/bin/python3 $ROOT/scripts/config.py browser)"

xtap auth browser --browser "$BROWSER" \
  || echo "WARN: cookie import failed; using existing session"
xtap sync bookmarks -n 200
python3 "$ROOT/scripts/x_bookmarks_ingest.py"
