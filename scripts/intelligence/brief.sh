#!/usr/bin/env bash
# Pre-engagement brief: the highest-value output of the brain. Before a call, a
# diligence, or a memo, answer in one pass: what has this person/company/theme
# claimed over time, where did they reverse, and how does it collide with the
# operator's active theses.
#
#   brief.sh <target-slug>
set -uo pipefail
SLUG="${1:-}"
[[ -n "$SLUG" ]] || { echo "usage: brief.sh <target-slug>" >&2; exit 1; }

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=../lib.sh
source "$ROOT/scripts/lib.sh"
MODEL="${BRAIN_BRIEF_MODEL:-claude-sonnet-5}"
OPERATOR="$(brain_py "$ROOT/scripts/config.py" identity.name 2>/dev/null || echo 'the operator')"
CONTEXT="$(brain_py "$ROOT/scripts/config.py" identity.context 2>/dev/null || echo '')"
CTX="$(mktemp -t "brief-$SLUG.XXXX")"
trap 'rm -f "$CTX"' EXIT
mkdir -p "$ROOT/Briefs" "$ROOT/.status"
OUT="$ROOT/Briefs/$SLUG-$(date +%Y-%m-%d).md"

brain_py "$ROOT/scripts/intelligence/brief_context.py" "$SLUG" > "$CTX" 2>/dev/null
[[ -s "$CTX" ]] || { echo "no context for $SLUG"; exit 2; }

claude -p "Write a pre-engagement brief for '$SLUG' to $OUT.

Session bootstrap (read these before writing, if present):
- Profile/00-overview.md
- Profile/working-with-me.md
- Profile/identity.md and other Profile notes as needed
- Theses/ for active positions that might collide

Operator: $OPERATOR. Config context line (secondary to Profile files): $CONTEXT.
This brief is what $OPERATOR reads before a call, a diligence, or a memo. Follow AGENTS.md voice (plain, dense, no em-dashes).

Graph/ledger context (ledger/claims, graph neighbors, theses index): $CTX  (Read it.)

Structure:
# Brief: <target> — <today's date>
## Arc on the key themes
For each theme where they have a track record: 2-4 dated beats showing how the view moved, each with a [[episode]] cite. Lead with reversals.
## Contradictions & reversals
The sharpest places they changed their mind or contradict themselves, dated.
## Thesis collision
For each of $OPERATOR's active theses that this target touches: does their track record confirm it, pressure it, or should it update the thesis? Name the thesis by [[wikilink]].
## Ask list (5)
Five specific questions $OPERATOR should ask them, derived from the gaps/reversals above.
## Kill criteria
The 2-3 things that, if true, mean walk away (for diligence) or that the thesis is wrong.

Be specific with numbers and dates from the context. If the context is thin, say so plainly rather than padding. Do not touch other files. Do not commit." \
  --model "$MODEL" --permission-mode acceptEdits --allowedTools "Read Write" \
  >> "$ROOT/.status/brief.log" 2>&1

[[ -f "$OUT" ]] && { echo "brief: $OUT"; } || { echo "FAILED: $SLUG"; exit 4; }
