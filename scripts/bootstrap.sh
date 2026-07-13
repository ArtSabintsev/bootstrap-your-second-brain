#!/usr/bin/env bash
# Bootstrap a brain from scratch: structure, venv, vendored xtap CLI, config,
# and the secrets dir. Idempotent. Run once after cloning, then edit config.json
# and drop your secrets in the secrets dir.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
echo "== brain bootstrap =="

# 1. per-user config
if [[ ! -f config.json ]]; then
  cp config.example.json config.json
  echo "created config.json from template — EDIT it with your handles/ids/browser"
fi

# 2. folder structure
for d in Sources Topics People Theses Library Briefs Drafts Clippings _indexes \
         Sources/x-bookmarks Sources/goodreads Sources/substack Sources/github; do
  mkdir -p "$d"
done

# 3. venv + deps + vendored X CLI (xtap)
[[ -d .venv ]] || python3 -m venv .venv
.venv/bin/pip install -q -e tools/xtap
.venv/bin/pip install -q httpx html2text openpyxl pypdf yt-dlp

# 4. secrets dir (never inside the vault)
SECRETS="$(.venv/bin/python3 scripts/config.py secrets_dir)"
SECRETS="${SECRETS/#\~/$HOME}"
mkdir -p "$SECRETS"
BROWSER="$(.venv/bin/python3 scripts/config.py browser)"

cat <<EOF

Bootstrap complete. Next steps:
  1. Edit config.json      (identity, browser=$BROWSER, secrets_dir)
  2. Secrets -> $SECRETS   (e.g. goodreads/rss-key). Never in the vault.
  3. Auth X:  .venv/bin/xtap auth browser --browser $BROWSER && .venv/bin/xtap auth whoami
  4. Podcasts: edit scripts/podcasts/shows.json for your shows
  5. Ensure the Claude and Grok CLIs are installed (intelligence layer + daily processing)
  6. Daily job: cp scripts/com.brain.ingest.plist ~/Library/LaunchAgents/ && \\
                launchctl load ~/Library/LaunchAgents/com.brain.ingest.plist
EOF
