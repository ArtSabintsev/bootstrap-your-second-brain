#!/usr/bin/env bash
# Health check for a second-brain vault. Exit 0 if critical checks pass;
# exit 1 if any critical check fails. Non-critical issues print as WARN.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=lib.sh
source "$ROOT/scripts/lib.sh"
cd "$ROOT"

FAIL=0
WARN=0

ok()   { printf '  OK   %s\n' "$*"; }
warn() { printf '  WARN %s\n' "$*"; WARN=$((WARN + 1)); }
fail() { printf '  FAIL %s\n' "$*"; FAIL=$((FAIL + 1)); }

echo "== brain doctor =="
echo "root: $ROOT"
echo "branch: $(brain_git_branch)"
echo

echo "-- critical --"
if [[ -f config.json ]]; then
  ok "config.json present"
else
  fail "config.json missing (run scripts/bootstrap.sh)"
fi

if [[ -x .venv/bin/python3 ]]; then
  ok "venv python"
else
  fail ".venv missing (run scripts/bootstrap.sh)"
fi

if [[ -x .venv/bin/xtap ]] || .venv/bin/python3 -c "import xtap" 2>/dev/null; then
  ok "xtap importable"
else
  fail "xtap not installed in venv"
fi

NAME="$(brain_py scripts/config.py identity.name 2>/dev/null || true)"
if [[ -n "$NAME" && "$NAME" != "Your Name" ]]; then
  ok "identity.name=$NAME"
else
  fail "identity.name still placeholder; edit config.json"
fi

for d in Profile Projects Meetings Log Sources Topics People Theses Library Briefs Digests Drafts Clippings _indexes; do
  if [[ -d "$d" ]]; then
    ok "dir $d/"
  else
    fail "missing dir $d/ (run bootstrap)"
  fi
done

if [[ -f Profile/00-overview.md && -f Profile/working-with-me.md ]]; then
  ok "Profile seed notes present"
else
  fail "Profile/00-overview.md or working-with-me.md missing"
fi

if command -v claude >/dev/null 2>&1; then
  ok "claude CLI on PATH"
else
  fail "claude CLI not on PATH (required for ingest/synth/ask)"
fi

echo
echo "-- sources (from config) --"
while IFS= read -r key; do
  [[ -z "$key" ]] && continue
  if brain_source_enabled "$key"; then
    printf '  ON   sources.%s\n' "$key"
  else
    printf '  OFF  sources.%s\n' "$key"
  fi
done < <(brain_py scripts/config.py --source-keys 2>/dev/null | brain_py -c 'import json,sys;print("\n".join(json.load(sys.stdin)))')

echo
echo "-- optional / source-specific --"
if command -v grok >/dev/null 2>&1; then
  ok "grok CLI on PATH"
else
  warn "grok CLI not on PATH (optional; ask.sh -m grok)"
fi

if brain_source_enabled github; then
  if command -v gh >/dev/null 2>&1; then
    if gh auth status >/dev/null 2>&1; then
      ok "gh authenticated"
    else
      fail "gh not authenticated (sources.github is on)"
    fi
  else
    fail "gh CLI missing (sources.github is on)"
  fi
else
  warn "github source off"
fi

if brain_source_enabled goodreads; then
  SECRETS="$(brain_py scripts/config.py secrets_dir 2>/dev/null || echo '')"
  SECRETS="${SECRETS/#\~/$HOME}"
  KEY="$SECRETS/goodreads/rss-key"
  if [[ -f "$KEY" && -s "$KEY" ]]; then
    ok "goodreads rss-key at $KEY"
  else
    fail "missing $KEY (sources.goodreads is on)"
  fi
  GR_UID="$(brain_py scripts/config.py identity.goodreads_user_id 2>/dev/null || true)"
  if [[ -n "$GR_UID" && "$GR_UID" != "00000000" ]]; then
    ok "goodreads_user_id=$GR_UID"
  else
    fail "identity.goodreads_user_id still placeholder"
  fi
else
  warn "goodreads source off"
fi

if brain_source_enabled substack; then
  FEED="$(brain_py scripts/config.py identity.substack_feed 2>/dev/null || true)"
  if [[ -n "$FEED" && "$FEED" != *"yourhandle"* ]]; then
    ok "substack_feed=$FEED"
  else
    fail "identity.substack_feed still placeholder (sources.substack is on)"
  fi
else
  warn "substack source off"
fi

if brain_source_enabled google_drive_meetings; then
  SECRETS="$(brain_py scripts/config.py secrets_dir 2>/dev/null || echo '')"
  SECRETS="${SECRETS/#\~/$HOME}"
  GTOKEN="$SECRETS/google-drive/token.json"
  if [[ -f "$GTOKEN" && -s "$GTOKEN" ]]; then
    ok "google-drive token at $GTOKEN"
  else
    fail "missing $GTOKEN (sources.google_drive_meetings is on; run scripts/google_drive_auth.py)"
  fi
else
  warn "google_drive_meetings source off"
fi

if brain_source_enabled x_bookmarks || brain_source_enabled youtube_likes; then
  if [[ -d "$HOME/.xtap" ]]; then
    ok "~/.xtap present (xtap home)"
  else
    warn "~/.xtap missing; run: .venv/bin/xtap auth browser"
  fi
fi

if brain_source_enabled podcasts; then
  if [[ -f scripts/podcasts/shows.json ]]; then
    COUNT="$(brain_py -c "import json;print(len(json.load(open('scripts/podcasts/shows.json'))))" 2>/dev/null || echo 0)"
    if [[ "$COUNT" -gt 0 ]]; then
      ok "shows.json has $COUNT show(s)"
    else
      fail "shows.json is empty but sources.podcasts is on: interview the operator for shows, find each channel/feed URL, fill scripts/podcasts/shows.json (schema: shows.example.json)"
    fi
  else
    fail "scripts/podcasts/shows.json missing (run bootstrap, then fill it; schema: shows.example.json)"
  fi
fi

echo
if [[ "$FAIL" -gt 0 ]]; then
  echo "RESULT: $FAIL failure(s), $WARN warning(s). Fix FAILs before relying on daily ingest."
  exit 1
fi
echo "RESULT: all critical checks passed ($WARN warning(s))."
exit 0
