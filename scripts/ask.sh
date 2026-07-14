#!/usr/bin/env bash
# Ask the brain. Routes a question to Claude or Grok, answered against the vault
# with citations. Free: uses the CLIs you already have, no plugin subscription,
# no vector database (the agents grep and read selectively).
#
#   ask.sh [-m claude|grok] [-s]  "your question"
#     -m  model (default: claude)
#     -s  save the answer to Briefs/ask-<n>.md instead of stdout
#
# Obsidian wiring (Shell Commands plugin): bind a hotkey to
#   scripts/ask.sh -m claude "{{selection}}"
# and set the command to insert output at the cursor.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=lib.sh
source "$ROOT/scripts/lib.sh"
cd "$ROOT"
OPERATOR="$(brain_py "$ROOT/scripts/config.py" identity.name 2>/dev/null || echo 'the operator')"
MODEL="claude"; SAVE=0
while getopts "m:s" opt; do
  case $opt in
    m) MODEL="$OPTARG" ;;
    s) SAVE=1 ;;
    *) ;;
  esac
done
shift $((OPTIND - 1))
Q="$*"
[[ -z "$Q" ]] && { echo "usage: ask.sh [-m claude|grok] [-s] \"question\"" >&2; exit 1; }

read -r -d '' PROMPT <<EOF || true
Answer this question against $OPERATOR's second-brain vault (this directory).

Session bootstrap (do this first for non-trivial questions):
- Read Profile/00-overview.md and Profile/working-with-me.md if present.
- Pull other Profile/ notes when the question is about priorities, identity,
  goals, or how $OPERATOR should decide.

Then search the intelligence layer and notes:
- Profile/ (who they are; wins over generic knowledge)
- Theses/ (dated positions + counter-evidence)
- Topics/ (canonical concepts), People/ (position ledgers)
- Log/ (recent decisions, lessons, kills)
- Library/, Briefs/, Drafts/, Projects/, todos.md
- _indexes/appearances.json (people/topics -> episodes graph)

Prefer what $OPERATOR has actually written and tracked over generic knowledge.
Cite the notes you used as [[wikilinks]]. Be specific and dense, in plain voice,
no em-dashes, no filler. If the honest answer is that the vault does not cover
this, say so rather than padding.

Question: $Q
EOF

run_claude() {
  claude -p "$PROMPT" --permission-mode plan \
    --allowedTools "Read Grep Glob Bash(git log:*)" 2>/dev/null
}
run_grok() { grok -p "$PROMPT" --output-format plain 2>/dev/null; }

case "$MODEL" in
  claude) OUT="$(run_claude)" ;;
  grok)   OUT="$(run_grok)" ;;
  both)   OUT="## Claude"$'\n\n'"$(run_claude)"$'\n\n'"## Grok"$'\n\n'"$(run_grok)" ;;
  *) echo "unknown model: $MODEL (use claude|grok|both)" >&2; exit 1 ;;
esac

if [[ "$SAVE" == "1" ]]; then
  mkdir -p Briefs
  n=$(ls Briefs/ask-*.md 2>/dev/null | wc -l | tr -d ' ')
  OUTFILE="Briefs/ask-$(printf '%03d' $((n+1))).md"
  printf '# Ask (%s)\n\n> %s\n\n%s\n' "$MODEL" "$Q" "$OUT" > "$OUTFILE"
  echo "saved: $OUTFILE"
else
  printf '%s\n' "$OUT"
fi
