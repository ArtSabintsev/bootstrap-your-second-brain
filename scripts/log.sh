#!/usr/bin/env bash
# Append a line to today's operator log (Log/YYYY-MM-DD.md).
#
#   scripts/log.sh "decision: killed idea X because Y"
#   scripts/log.sh lesson "Profile must load first"
#
# First arg may be a kind (decision|lesson|idea|kill|note); remaining args are
# the body. If the first arg is not a known kind, the whole list is the body.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p Log

DAY="$(date +%Y-%m-%d)"
TIME="$(date +%H:%M)"
FILE="Log/$DAY.md"

KIND="note"
if [[ $# -ge 2 ]]; then
  case "$1" in
    decision|lesson|idea|kill|note)
      KIND="$1"
      shift
      ;;
  esac
fi

BODY="$*"
[[ -n "$BODY" ]] || { echo "usage: log.sh [decision|lesson|idea|kill] <text>" >&2; exit 1; }

if [[ ! -f "$FILE" ]]; then
  cat > "$FILE" <<EOF
---
title: "Log $DAY"
type: log
tags: [unsorted]
created: $DAY
updated: $DAY
---

# Log — $DAY

EOF
fi

printf -- '- **%s** (%s): %s\n' "$KIND" "$TIME" "$BODY" >> "$FILE"

if grep -q '^updated:' "$FILE"; then
  sed -i '' "s/^updated:.*/updated: $DAY/" "$FILE" 2>/dev/null \
    || sed -i "s/^updated:.*/updated: $DAY/" "$FILE"
fi

echo "logged: $FILE ($KIND)"
