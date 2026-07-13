#!/usr/bin/env bash
# Synthesize ONE liked video into a note IF it is substantive. The Sonnet worker
# judges: music, DJ sets, gameplay, streams, comedy, and no-substance videos are
# skipped (recorded so re-runs don't re-fetch them). Writes only its own note.
#
#   synth_like.sh <video_id> <duration_s> <channel> <title>
#
# Exit: 0 wrote note, 5 already done, 7 judged not-substantive, 3 no transcript.
set -uo pipefail

VID="$1"; DUR="$2"; CHANNEL="$3"; shift 3; TITLE="$*"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HERE="$ROOT/scripts"
MODEL="${BRAIN_LIKE_MODEL:-claude-sonnet-5}"
OPERATOR="$("$ROOT/.venv/bin/python3" "$ROOT/scripts/config.py" identity.name 2>/dev/null || echo 'the operator')"
INTERESTS="$("$ROOT/.venv/bin/python3" "$ROOT/scripts/config.py" identity.interests 2>/dev/null || echo 'see scripts/ontology.yaml')"
SKIP_LOG="$ROOT/.status/youtube-likes-skip.log"
mkdir -p "$ROOT/.status"

# already judged non-substantive or unavailable?
[[ -f "$SKIP_LOG" ]] && grep -q "^$VID " "$SKIP_LOG" && { echo "skip (judged): $VID"; exit 7; }

slug() { echo "$1" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+|-+$//g' | cut -c1-70; }
NOTE_DIR="$ROOT/Library/youtube-likes"
NOTE="$NOTE_DIR/$(slug "$CHANNEL")-$(slug "$TITLE").md"
[[ -f "$NOTE" ]] && { echo "skip (exists): $VID"; exit 5; }

TX="$(mktemp -t "yt-$VID.XXXX")"
trap 'rm -f "$TX"' EXIT
if ! "$HERE/podcasts/fetch_transcript.py" "$VID" "$TX" >/dev/null 2>&1 || [[ ! -s "$TX" ]]; then
  echo "$VID no-transcript $CHANNEL" >> "$SKIP_LOG"
  echo "no transcript: $VID"; exit 3
fi
mkdir -p "$NOTE_DIR"

claude -p "You are judging and possibly synthesizing one YouTube video the operator liked, into $OPERATOR's Obsidian vault (voice: plain, dense, no em-dashes). Follow AGENTS.md.

Video: '$TITLE'
Channel: $CHANNEL   Duration: $((DUR/60)) min
URL: https://www.youtube.com/watch?v=$VID
Transcript: $TX  (Read it first.)

FIRST decide if this is worth a permanent knowledge note. Write a note ONLY if it has real intellectual substance: a lecture, argument, teaching, debate, interview, explainer, or documentary on religion, theology, biblical/Jewish text, history, philosophy, science, technology, business, or similar. Do NOT write a note for music, DJ sets, concerts, gameplay, game streams/reviews, comedy sketches, reaction videos, vlogs, kids' or children's content (cartoons, nursery rhymes, toy/family channels; the account may be shared with family, so skip kids' content), or anything with no substantive ideas. If it is not worth a note, do NOT create any file; just reply with the single word SKIP.

If it IS substantive, write a deep note to EXACTLY this path and nothing else: $NOTE
Frontmatter (title, tags from the approved list, created, updated, source: the URL). Then:
- ## Source — who is speaking/teaching (channel/author) and what this is, one or two lines. Wikilink notable people as [[firstname-lastname]].
- ## Core claims & arguments — the 8-15 most substantive points, each one tight sentence, quoting memorable lines where earned.
- ## Notable segments — the 3-6 passages worth remembering.
- ## Threads — wikilink the topics and themes as [[kebab-case-topic]], connecting to the operator's interests (see scripts/ontology.yaml and config identity.interests: $INTERESTS). A later pass builds the graph, so just write the wikilinks; do not create their target files. Do not touch People/, Topics/, or Sources/. Do not commit." \
  --model "$MODEL" --permission-mode acceptEdits --allowedTools "Read Write" \
  >> "$ROOT/.status/youtube-likes-claude.log" 2>&1

if [[ -f "$NOTE" ]]; then
  echo "done: $VID $CHANNEL"
else
  echo "$VID not-substantive $CHANNEL" >> "$SKIP_LOG"
  echo "skip (not substantive): $VID $CHANNEL"; exit 7
fi
