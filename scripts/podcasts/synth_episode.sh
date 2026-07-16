#!/usr/bin/env bash
# Phase 1 worker: synthesize ONE episode into its own note. Writes only
# that note (no People/Topics edits), so many of these run in parallel safely.
# Phase 2 (build_links.py) materializes the People/Topics graph afterward.
#
#   synth_episode.sh <show_key> <episode_id> <YYYYMMDD> <title>
#
# Idempotent: exits early if the note exists. No git. Transcript discarded
# for YouTube shows; RSS world-context shows use publisher show notes.
set -uo pipefail

SHOW="$1"; VID="$2"; DATE="$3"; shift 3; TITLE="$*"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HERE="$ROOT/scripts/podcasts"
MODEL="${BRAIN_POD_MODEL:-claude-sonnet-5}"
PY="$ROOT/.venv/bin/python3"
OPERATOR="$("$PY" "$ROOT/scripts/config.py" identity.name 2>/dev/null || echo 'the operator')"

slug() { echo "$1" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+|-+$//g' | cut -c1-60; }
ISO="${DATE:0:4}-${DATE:4:2}-${DATE:6:2}"
NOTE_DIR="$ROOT/Library/podcasts/$SHOW"
NOTE="$NOTE_DIR/${ISO}-$(slug "$TITLE").md"
[[ -f "$NOTE" ]] && { echo "skip (exists): $SHOW $VID"; exit 5; }

SOURCE="$("$PY" -c "import json;print(json.load(open('$HERE/shows.json'))['$SHOW'].get('source','youtube'))")"
ROLE="$("$PY" -c "import json;print(json.load(open('$HERE/shows.json'))['$SHOW'].get('role',''))")"
SHOW_TITLE="$("$PY" -c "import json;print(json.load(open('$HERE/shows.json'))['$SHOW'].get('title','$SHOW'))")"

TX="$(mktemp -t "pod-$VID.XXXX")"
trap 'rm -f "$TX"' EXIT

if [[ "$SOURCE" == "rss" ]]; then
  "$PY" "$HERE/fetch_rss_episode.py" "$SHOW" "$VID" "$TX" >/dev/null 2>&1
  rc=$?
  { [[ $rc -ne 0 ]] || [[ ! -s "$TX" ]]; } && { echo "no rss payload: $SHOW $VID"; exit 3; }

  # World-context shows: do NOT write per-episode notes (vault bloat).
  # Monthly digests via consolidate_world_context.py only.
  if [[ "$ROLE" == "world-context" ]]; then
    echo "skip (world-context is monthly-only): $SHOW $VID — run consolidate_world_context.py"
    exit 5
  fi

  # Other RSS shows: Claude synthesis on show notes (no captions).
  mkdir -p "$NOTE_DIR"
  claude -p "You are processing one podcast episode into $OPERATOR's Obsidian vault. Follow AGENTS.md voice (plain, dense, no em-dashes).

Episode: '$TITLE' from the show '$SHOW_TITLE' (key=$SHOW), published $ISO.
Episode id: $VID
Show notes / description (not a full transcript): $TX  (Read it in full first.)

Write a DEEP synthesis note to EXACTLY this path, and write NOTHING else: $NOTE
Do not create or edit any other file. Do not touch People/, Topics, or Sources/.

Frontmatter: title, tags (from the approved list), created: $ISO, updated: $ISO, source: episode link if present in the notes file.
Then Guests / Core claims / Notable segments / Threads with [[wikilinks]] as usual.
Ignore ads and sponsor reads." \
    --model "$MODEL" --permission-mode acceptEdits --allowedTools "Read Write" \
    >> "$ROOT/.status/podcasts-claude.log" 2>&1
  if [[ -f "$NOTE" ]]; then echo "done: $SHOW $VID $ISO"; else echo "FAILED: $SHOW $VID"; exit 4; fi
  exit 0
fi

# YouTube path (default)
"$PY" "$HERE/fetch_transcript.py" "$VID" "$TX" >/dev/null 2>&1
rc=$?
[[ $rc -eq 42 ]] && { echo "RATE_LIMITED: $SHOW $VID"; exit 8; }
{ [[ $rc -ne 0 ]] || [[ ! -s "$TX" ]]; } && { echo "no transcript: $SHOW $VID"; exit 3; }
mkdir -p "$NOTE_DIR"

claude -p "You are processing one podcast episode into $OPERATOR's Obsidian vault. Follow AGENTS.md voice (plain, dense, no em-dashes).

Episode: '$TITLE' from the show '$SHOW', published $ISO.
YouTube: https://www.youtube.com/watch?v=$VID
Cleaned transcript: $TX  (Read it in full first.)

Write a DEEP synthesis note to EXACTLY this path, and write NOTHING else: $NOTE
Do not create or edit any other file. Do not touch People/, Topics/, or Sources/. A later pass builds the link graph from the wikilinks you write here, so just WRITE the wikilinks inline; do not create their target files.

Frontmatter: title, tags (from the approved list), created: $ISO, updated: $ISO, source: the YouTube URL. Then:
- ## Guests — each speaker, one line on who they are. Wikilink every named person as [[firstname-lastname]] in lowercase kebab-case (e.g. [[ada-lovelace]], [[alan-turing]]). Use that exact canonical slug form so links from different episodes converge on one person.
- ## Core claims & predictions — the 8-15 most substantive, specific claims/arguments/forecasts, each one tight sentence, quoting a memorable line where it earns it. No filler.
- ## Notable segments — the 3-6 exchanges worth remembering, with context.
- ## Threads — wikilink the topics and themes this episode advances as [[kebab-case-topic]] (e.g. [[ai-capex-bubble]], [[frontier-vs-open-source-ai]]), and wikilink any people again. Use stable, general topic slugs so episodes converge on shared topics.

Ignore all advertising: host-read sponsor spots, promo codes, 'brought to you by', merch/subscription plugs, and self-promotion are noise; never record them as claims or segments. A permanent knowledge asset, not a summary. Do not commit." \
  --model "$MODEL" --permission-mode acceptEdits --allowedTools "Read Write" \
  >> "$ROOT/.status/podcasts-claude.log" 2>&1

if [[ -f "$NOTE" ]]; then echo "done: $SHOW $VID $ISO"; else echo "FAILED: $SHOW $VID"; exit 4; fi
