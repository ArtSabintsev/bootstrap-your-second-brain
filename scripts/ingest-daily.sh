#!/usr/bin/env bash
# Daily multi-source ingest for the brain vault. Safe for launchd/cron.
#
# Sources run independently; one failing does not block the others:
#   x-bookmarks  -> Sources/x-bookmarks/   (vendored xtap CLI)
#   goodreads    -> Sources/goodreads/     (private all-shelves RSS)
#   substack     -> Sources/substack/      (publication feed)
#   github       -> Sources/github/        (gh CLI, recent commits)
#   podcasts     -> Library/podcasts/      (new episodes, deep synthesis)
#
# Then, if anything new landed: one Claude pass enriches (follows links, does
# web research) and files substantive items into the wiki (skip with
# BRAIN_PROCESS=0), then one commit. Syncs with the remote: pull --rebase
# before running, push when done (the standing exception to the vault's
# never-push rule; see AGENTS.md).
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$ROOT/.status"
mkdir -p "$LOG_DIR"

OPERATOR="$("$ROOT/.venv/bin/python3" "$ROOT/scripts/config.py" identity.name 2>/dev/null || echo 'the operator')"

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }

cd "$ROOT"
log "git pull --rebase"
if ! git pull --rebase --autostash origin main; then
  git rebase --abort 2>/dev/null || true
  log "ERROR: pull --rebase hit a conflict; aborting run, vault untouched"
  exit 1
fi

run_source() {
  local name="$1"; shift
  log "source: $name"
  if "$@"; then
    log "source: $name ok"
  else
    log "WARN: source $name failed (exit $?); continuing"
  fi
}

run_source x-bookmarks "$ROOT/scripts/sources/x-bookmarks.sh"
run_source goodreads "$ROOT/.venv/bin/python3" "$ROOT/scripts/goodreads_ingest.py"
run_source substack "$ROOT/.venv/bin/python3" "$ROOT/scripts/substack_ingest.py"
run_source github "$ROOT/.venv/bin/python3" "$ROOT/scripts/github_ingest.py" --days 3

# PROCESS_OK gates platform cleanup: bookmarks are removed from X only after
# they are both archived and processed (or there was nothing new to process).
PROCESS_OK=1
if [[ -z "$(git status --porcelain Sources/)" ]]; then
  log "no new captures; nothing to commit"
else
  PROCESS_OK=0
  if [[ "${BRAIN_PROCESS:-1}" == "1" ]] && command -v claude >/dev/null 2>&1; then
    log "processing new captures with claude"
    claude -p "New captures were just appended under Sources/ (x-bookmarks, goodreads, substack, and/or github; see 'git status Sources/'). Follow AGENTS.md. For each substantive new item: enrich, analyze, then file. Enrich: follow the item's links with WebFetch (t.co redirects, linked articles, threads) and read what the source actually says, not just the capture text; use WebSearch when a claim needs context or verification. Analyze: go beyond summary — what does this signal for the market or space it belongs to, what are the second-order effects, and how does it connect to $OPERATOR's existing theses and notes (example: a bookmark about Starbucks dropping Microsoft/IBM for bespoke software isn't 'Starbucks news', it's a data point about AI collapsing the cost of internal software and what that does to enterprise vendors — capture that inference). For the github capture, fold the recent commits into the relevant Projects/ notes so the vault tracks what $OPERATOR is actively building (what shipped, what changed, current state); do not make a note per commit. File other items into Topics/, Library/, or People/ with proper frontmatter, tags from the approved tag list, wikilinks to related notes, and the source URL. Leave throwaway items (memes, one-liners with no substance) unfiled. Append one line per filed item to .status/filed.log in the form 'YYYY-MM-DD <capture item> -> <note path>'. Do not edit anything under Sources/. Do not commit or push; the calling script does." \
      --permission-mode acceptEdits --allowedTools "Read Write Edit WebSearch WebFetch Bash" >> "$LOG_DIR/ingest-claude.log" 2>&1 \
      && PROCESS_OK=1 \
      || log "WARN: claude processing failed; captures are still archived"
  fi

  git add -A Sources Topics Library People
  git commit -m "Daily ingest $(date +%Y-%m-%d)" --quiet || log "nothing to commit"
fi

if [[ "${BRAIN_X_DELETE:-1}" == "1" && "$PROCESS_OK" == "1" ]]; then
  log "cleanup: removing archived+processed bookmarks from X"
  "$ROOT/.venv/bin/python3" "$ROOT/scripts/x_bookmarks_cleanup.py" \
    || log "WARN: X bookmark cleanup failed; will retry next run"
else
  log "cleanup skipped (processing incomplete or BRAIN_X_DELETE=0)"
fi

log "git push"
git push origin main || log "WARN: push failed; commits remain local"

# New podcast episodes: only look back a couple weeks so old episodes trip the
# stale-stop quickly. backfill.sh dedupes and self-commits/pushes.
if [[ "${BRAIN_PODCASTS:-1}" == "1" ]] && command -v claude >/dev/null 2>&1; then
  log "podcasts: pulling new episodes"
  CUTOFF="$(date -v-14d +%Y%m%d 2>/dev/null || date -d '14 days ago' +%Y%m%d)" \
    STALE_STOP=3 "$ROOT/scripts/podcasts/backfill.sh" \
    >> "$LOG_DIR/podcasts.log" 2>&1 \
    || log "WARN: podcast pull failed; will retry next run"
fi

# New long-form YouTube likes (live LL pull; only unprocessed >=20min are judged).
if [[ "${BRAIN_LIKES:-1}" == "1" ]] && command -v claude >/dev/null 2>&1; then
  log "youtube-likes: pulling new likes"
  JOBS=2 "$ROOT/scripts/youtube_likes/run.sh" 1200 \
    >> "$LOG_DIR/youtube-likes.log" 2>&1 \
    || log "WARN: youtube-likes pull failed; will retry next run"
fi

log "done"
