#!/usr/bin/env bash
# Build/refresh a person's position ledger: how their views changed over time,
# dated, with citations. This is the evolution-of-thought layer. Reads only the
# claims digest (not transcripts), so it is cheap.
#
#   build_ledger.sh <person-slug>
set -uo pipefail
SLUG="$1"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
MODEL="${BRAIN_LEDGER_MODEL:-claude-sonnet-5}"
NOTE="$ROOT/People/$SLUG.md"
DIGEST="$(mktemp -t "ledger-$SLUG.XXXX")"
trap 'rm -f "$DIGEST"' EXIT

"$ROOT/.venv/bin/python3" "$ROOT/scripts/intelligence/person_claims.py" "$SLUG" 50 > "$DIGEST" 2>/dev/null
[[ -s "$DIGEST" ]] || { echo "no claims digest for $SLUG"; exit 2; }

EXISTING=""
[[ -f "$NOTE" ]] && EXISTING="A note already exists at $NOTE; preserve its bio/frontmatter and REPLACE its position-ledger section."

claude -p "Build a position ledger for [[$SLUG]] into $NOTE. Follow AGENTS.md voice (plain, dense, no em-dashes). $EXISTING

Input digest of their dated claims across podcast appearances: $DIGEST (Read it).

The note must be a PERSON note with:
- frontmatter: title, type: person, tier: core, tags, updated (today).
- one-line identity.
- ## Position ledger, organized by THEME (e.g. 'AI ROI', 'Crypto/tokens', 'US-China', 'Rates & macro'). Under each theme a markdown table:
  | date | stance | claim (<=22 words) | cite |
  where stance is one of bull/bear/skeptic/neutral/reversed/hedging, and cite is the [[episode-note-slug]] wikilink from the digest heading.
  Only record a row when the view is stated, changes, or deepens. Collapse repeats. Newest-first within a theme.
- After each theme's table, a one-line **Arc:** summarizing the trajectory and the next reversal to watch for.
- Keep it to the 3-6 themes where this person actually has a track record. Ignore ad reads and filler.

This is the intelligence layer, not a transcript. Be specific with numbers and dates. Do not touch other files. Do not commit." \
  --model "$MODEL" --permission-mode acceptEdits --allowedTools "Read Write Edit" \
  >> "$ROOT/.status/ledger.log" 2>&1

[[ -f "$NOTE" ]] && echo "ledger: $SLUG -> People/$SLUG.md" || { echo "FAILED: $SLUG"; exit 4; }
