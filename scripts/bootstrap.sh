#!/usr/bin/env bash
# Bootstrap a brain from scratch: structure, venv, vendored xtap CLI, config,
# Profile seeds, secrets dir, and launchd path rewrite. Idempotent.
# See SETUP.md for the full walkthrough (human or AI agent).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
echo "== brain bootstrap =="

# 1. per-user config
if [[ ! -f config.json ]]; then
  cp config.example.json config.json
  echo "created config.json from template — EDIT it with your handles/ids/browser"
fi

# 2. folder structure (matches AGENTS.md)
for d in Sources Topics People Theses Library Briefs Log Drafts Clippings \
         Profile Projects _indexes \
         Sources/x-bookmarks Sources/goodreads Sources/substack Sources/github \
         Sources/meeting-notes Meetings Digests \
         Library/podcasts Library/youtube-likes; do
  mkdir -p "$d"
  # keep empty dirs in git when cloning without seeds
  [[ -f "$d/.gitkeep" ]] || touch "$d/.gitkeep" 2>/dev/null || true
done

# 3. venv + deps + vendored X CLI (xtap)
[[ -d .venv ]] || python3 -m venv .venv
.venv/bin/pip install -q -e tools/xtap
.venv/bin/pip install -q httpx html2text openpyxl pypdf yt-dlp google-api-python-client google-auth-oauthlib

# shellcheck source=lib.sh
source "$ROOT/scripts/lib.sh"

# 4. secrets dir (never inside the vault)
SECRETS="$(brain_py scripts/config.py secrets_dir)"
SECRETS="${SECRETS/#\~/$HOME}"
mkdir -p "$SECRETS"
if [[ "$(brain_py scripts/config.py --source-enabled goodreads)" == "true" ]]; then
  mkdir -p "$SECRETS/goodreads"
fi
BROWSER="$(brain_py scripts/config.py browser)"
NAME="$(brain_py scripts/config.py identity.name 2>/dev/null || echo 'Your Name')"
CONTEXT="$(brain_py scripts/config.py identity.context 2>/dev/null || echo '')"
TODAY="$(date +%Y-%m-%d)"

# 4b. podcast shows: operator-populated (interview + find URLs; see SETUP.md).
# Ship none; create an empty registry so scripts have a file to read.
if [[ ! -f scripts/podcasts/shows.json ]]; then
  printf '{}\n' > scripts/podcasts/shows.json
  echo "created empty scripts/podcasts/shows.json (fill via SETUP.md step 5; schema: scripts/podcasts/shows.example.json)"
fi

# 5. Profile seeds. Write when the file is missing OR still the shipped
# placeholder stub ("Replace this stub"); never overwrite operator edits.
seed_profile() {
  local path="$1"
  local content="$2"
  if [[ ! -f "$path" ]] || grep -q "Replace this stub" "$path" 2>/dev/null; then
    printf '%s\n' "$content" > "$path"
    echo "seeded $path"
  fi
}

seed_profile "Profile/00-overview.md" "---
title: \"Overview\"
type: profile
tags: [unsorted]
created: $TODAY
updated: $TODAY
---

# Overview

**$NAME.** Replace this stub with who you are, what you build, and what this
vault is for. One screen max. Agents read this first on non-trivial sessions.

Context line from config: $CONTEXT

Related: [[identity]] · [[working-with-me]]
"

seed_profile "Profile/identity.md" "---
title: \"Identity\"
type: profile
tags: [unsorted]
created: $TODAY
updated: $TODAY
---

# Identity

- Name: $NAME
- One-line context: $CONTEXT
- Interests: see config.json identity.interests (and expand here in prose)

Fill in handles, roles, and how you want to be described in briefs.
"

seed_profile "Profile/working-with-me.md" "---
title: \"Working With Me\"
type: profile
tags: [unsorted]
created: $TODAY
updated: $TODAY
---

# Working With Me

How agents should operate with you. Edit freely.

## Voice and stance

- Be direct and precise. No flattery. If the operator is wrong, say so.
- Prefer vault notes and Profile over generic training knowledge.
- Use explicit confidence levels (high / moderate / low / unknown).
- No em dashes in drafted prose.

## Logging

- \"log this\" / \"remember this\" / \"kill this idea\" append to \`Log/YYYY-MM-DD.md\` only.
- Do not mint Topics from a log command.

## Environment

- Vault root: this repository
- Secrets: outside the vault in secrets_dir (see config.json)
"

if [[ ! -f todos.md ]]; then
  cat > todos.md <<EOF
---
title: "Todos"
type: todo
tags: [unsorted]
created: $TODAY
updated: $TODAY
---

# Todos

Open actions. Agents may add items during ingest when asked; check them off
when done.

## Open

- [ ] Fill Profile/00-overview.md and Profile/working-with-me.md
- [ ] Finish config.json (identity + sources toggles)
- [ ] Place secrets under secrets_dir (see secrets.example/README.md)
- [ ] Run scripts/doctor.sh and fix FAILs
- [ ] Auth X: .venv/bin/xtap auth browser
- [ ] Install daily job (see SETUP.md)

## Done

EOF
  echo "seeded todos.md"
fi

if [[ ! -f Log/README.md ]]; then
  cat > Log/README.md <<EOF
---
title: "Log"
type: index
tags: [unsorted]
created: $TODAY
updated: $TODAY
---

# Log

Append-only dated operator journal. One file per day: \`YYYY-MM-DD.md\`.

\`\`\`bash
scripts/log.sh decision "killed idea X because Y"
# or in chat: "log this: …"
\`\`\`

See AGENTS.md (Operator log section).
EOF
  echo "seeded Log/README.md"
fi

if [[ ! -f Projects/README.md ]]; then
  cat > Projects/README.md <<EOF
---
title: "Projects"
type: index
tags: [unsorted]
created: $TODAY
updated: $TODAY
---

# Projects

One note per thing you build or run. The daily GitHub ingest folds recent
commits into these notes. Create a note when a project becomes real.
EOF
  echo "seeded Projects/README.md"
fi

# 6. Rewrite launchd plist to this clone's path
PLIST="$ROOT/scripts/com.brain.ingest.plist"
if [[ -f "$PLIST" ]]; then
  export BRAIN_ROOT="$ROOT"
  brain_py - <<'PY'
from pathlib import Path
import os, re
root = os.environ["BRAIN_ROOT"]
p = Path(root) / "scripts" / "com.brain.ingest.plist"
text = p.read_text()
new = f'"{root}/scripts/ingest-daily.sh"'
text2, n = re.subn(
    r'(<string>)-lc</string>\s*<string>.*?ingest-daily\.sh.*?</string>',
    rf"\1-lc</string>\n    <string>{new}</string>",
    text,
    count=1,
    flags=re.DOTALL,
)
if not n:
    text2 = text
    print("launchd plist path left unchanged (edit scripts/com.brain.ingest.plist manually)")
else:
    print("rewrote launchd path ->", new)

# Run time from config (schedule.ingest_hour / ingest_minute, default 05:00)
import sys
sys.path.insert(0, str(Path(root) / "scripts"))
import config as _cfg
hour = int(_cfg.get("schedule.ingest_hour", 5) or 5)
minute = int(_cfg.get("schedule.ingest_minute", 0) or 0)
text2 = re.sub(r"<key>Hour</key>\s*<integer>\d+</integer>",
               f"<key>Hour</key>\n    <integer>{hour}</integer>", text2)
text2 = re.sub(r"<key>Minute</key>\s*<integer>\d+</integer>",
               f"<key>Minute</key>\n    <integer>{minute}</integer>", text2)
p.write_text(text2)
print(f"launchd schedule -> {hour:02d}:{minute:02d}")
PY
fi

# 7. Obsidian community plugins (builds stay untracked; config is in .obsidian/)
# Declared in .obsidian/community-plugins.json; hotkeys in .obsidian/hotkeys.json.
install_obsidian_plugin() {
  local id="$1" repo="$2"
  shift 2
  local dest=".obsidian/plugins/$id"
  mkdir -p "$dest"
  local f url
  for f in "$@"; do
    if [[ "$f" == *://* ]]; then
      # optional extra: "filename|url"
      local name="${f%%|*}"
      url="${f#*|}"
      if [[ ! -f "$dest/$name" ]]; then
        echo "  downloading $id/$name"
        curl -fsSL "$url" -o "$dest/$name"
      fi
    else
      url="https://github.com/${repo}/releases/latest/download/${f}"
      if [[ ! -f "$dest/$f" ]]; then
        echo "  downloading $id/$f"
        curl -fsSL "$url" -o "$dest/$f"
      fi
    fi
  done
  if [[ -f "$dest/manifest.json" ]]; then
    echo "  ok $id ($(python3 -c "import json; print(json.load(open('$dest/manifest.json'))['version'])" 2>/dev/null || echo '?'))"
  else
    echo "  WARN: $id missing manifest.json" >&2
  fi
}

echo "installing Obsidian plugins into .obsidian/plugins/ ..."
install_obsidian_plugin omnisearch scambier/obsidian-omnisearch \
  main.js manifest.json styles.css
install_obsidian_plugin ghostty-terminal lavs9/obsidian-ghostty-terminal \
  main.js manifest.json styles.css \
  "pty_helper.py|https://raw.githubusercontent.com/lavs9/obsidian-ghostty-terminal/main/pty_helper.py"
install_obsidian_plugin realclaudian YishenTu/claudian \
  main.js manifest.json styles.css

chmod +x scripts/*.sh scripts/intelligence/*.sh scripts/podcasts/*.sh scripts/youtube_likes/*.sh scripts/sources/*.sh 2>/dev/null || true

cat <<EOF

Bootstrap complete (incl. Obsidian plugins if network ok). Next steps (SETUP.md):
  1. Edit config.json      (identity, browser=$BROWSER, secrets_dir, sources)
  2. Secrets -> $SECRETS   (e.g. goodreads/rss-key). Never in the vault.
  3. Fill Profile/         (00-overview.md, working-with-me.md)
  4. Auth X:  .venv/bin/xtap auth browser --browser $BROWSER && .venv/bin/xtap auth whoami
  5. Podcasts: have your agent interview you for shows you follow, find each\n     channel/feed URL, and fill scripts/podcasts/shows.json (schema: shows.example.json)
  6. Doctor:  bash scripts/doctor.sh
  7. Ensure claude (and optionally grok) CLIs are installed
  8. Daily job: cp scripts/com.brain.ingest.plist ~/Library/LaunchAgents/ && \\
                launchctl load ~/Library/LaunchAgents/com.brain.ingest.plist
EOF
