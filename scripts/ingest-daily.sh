#!/usr/bin/env bash
# Daily multi-source ingest for the brain vault. Safe for launchd/cron.
#
# Sources run independently (each toggled in config.json under sources); one
# failing does not block the others:
#   x_bookmarks  -> Sources/x-bookmarks/   (vendored xtap CLI)
#   goodreads    -> Sources/goodreads/     (private all-shelves RSS)
#   substack     -> Sources/substack/      (publication feed)
#   github       -> Sources/github/        (gh CLI, recent commits)
#   podcasts     -> Library/podcasts/      (new episodes, deep synthesis)
#   google_drive_meetings -> Sources/meeting-notes/ (Google Meet's Notes-by-
#                            Gemini docs; filed into Meetings/<project>.md)
#   youtube_likes -> Library/youtube-likes/
#
# Then, if anything new landed: one Claude pass enriches (follows links, does
# web research) and files substantive items into the wiki (skip with
# BRAIN_PROCESS=0), then one commit. Syncs with the remote: pull --rebase
# before running, push when done (the standing exception to the vault's
# never-push rule; see AGENTS.md).
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=lib.sh
source "$ROOT/scripts/lib.sh"
LOG_DIR="$ROOT/.status"
mkdir -p "$LOG_DIR"

OPERATOR="$(brain_py "$ROOT/scripts/config.py" identity.name 2>/dev/null || echo 'the operator')"

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }

cd "$ROOT"
BRANCH="$(brain_git_branch)"
log "git pull --rebase origin $BRANCH"
if ! brain_git_pull; then
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

if brain_source_enabled x_bookmarks; then
  run_source x-bookmarks "$ROOT/scripts/sources/x-bookmarks.sh"
else
  log "source: x-bookmarks skipped (config.sources.x_bookmarks=false)"
fi

if brain_source_enabled goodreads; then
  run_source goodreads brain_py "$ROOT/scripts/goodreads_ingest.py"
else
  log "source: goodreads skipped (config.sources.goodreads=false)"
fi

if brain_source_enabled substack; then
  run_source substack brain_py "$ROOT/scripts/substack_ingest.py"
else
  log "source: substack skipped (config.sources.substack=false)"
fi

if brain_source_enabled github; then
  run_source github brain_py "$ROOT/scripts/github_ingest.py" --days 3
else
  log "source: github skipped (config.sources.github=false)"
fi

if brain_source_enabled google_drive_meetings; then
  run_source google-drive-meetings brain_py "$ROOT/scripts/google_drive_meetings_ingest.py"
else
  log "source: google-drive-meetings skipped (config.sources.google_drive_meetings=false)"
fi

# PROCESS_OK gates platform cleanup: bookmarks are removed from X only after
# they are both archived and processed (or there was nothing new to process).
PROCESS_OK=1
if [[ -z "$(git status --porcelain Sources/)" ]]; then
  log "no new captures; nothing to commit"
else
  PROCESS_OK=0
  if [[ "${BRAIN_PROCESS:-1}" == "1" ]]; then
    PROCESS_PROMPT="New captures were just appended under Sources/ (x-bookmarks, goodreads, substack, github, and/or meeting-notes; see 'git status Sources/'). Follow AGENTS.md. For each substantive new item: enrich, analyze, then file. Enrich: follow the item's links with WebFetch (t.co redirects, linked articles, threads) and read what the source actually says, not just the capture text; use WebSearch when a claim needs context or verification. Analyze: go beyond summary — what does this signal for the market or space it belongs to, what are the second-order effects, and how does it connect to $OPERATOR's existing theses and notes (example: a bookmark about Starbucks dropping Microsoft/IBM for bespoke software isn't 'Starbucks news', it's a data point about AI collapsing the cost of internal software and what that does to enterprise vendors — capture that inference). For the github capture, fold the recent commits into the relevant Projects/ notes so the vault tracks what $OPERATOR is actively building (what shipped, what changed, current state); do not make a note per commit. For meeting-notes captures (Sources/meeting-notes/): identify which counterparty/project each doc is about from its title and attendees, append a new dated entry to the matching Meetings/<project>.md (create it if it doesn't exist, as a dated log, newest entry on top, cross-linked back to the Projects/ note), and pull any facts that belong in the canonical Projects/ synthesis (new people, role scope, decisions) up into that note. If no matching project exists, leave it unfiled and note that in filed.log rather than guessing. File other items into Topics/, Library/, or People/ with proper frontmatter, tags from the approved tag list, wikilinks to related notes, and the source URL. Leave throwaway items (memes, one-liners with no substance) unfiled. Evolve the intelligence layer as you file: when a capture contains a substantive dated claim by someone with a People/ note, append a dated row (stance, claim, cite) to that person's position ledger and adjust the arc line; when a capture bears on a thesis in Theses/, append a dated timeline entry there, or add it to the counter-evidence queue if it cuts against. Never rewrite prior ledger or timeline rows. Append one line per filed item to .status/filed.log in the form 'YYYY-MM-DD <capture item> -> <note path>'. Do not edit anything under Sources/. Do not commit or push; the calling script does."
    # Sliding scale: walk config models.process (best model first) until one
    # CLI/model pair is installed and succeeds. See scripts/config.py.
    while IFS=$'\t' read -r RUNNER MODEL; do
      case "$RUNNER" in
        claude)
          command -v claude >/dev/null 2>&1 || { log "process: claude CLI missing; skipping ${MODEL:-claude-default}"; continue; }
          log "processing new captures with claude ${MODEL:-default}"
          if claude -p "$PROCESS_PROMPT" ${MODEL:+--model "$MODEL"} \
            --permission-mode acceptEdits --allowedTools "Read Write Edit WebSearch WebFetch Bash" \
            >> "$LOG_DIR/ingest-claude.log" 2>&1; then
            PROCESS_OK=1; log "process: filed by claude ${MODEL:-default}"; break
          fi
          log "WARN: claude ${MODEL:-default} failed; sliding to next model"
          ;;
        grok)
          command -v grok >/dev/null 2>&1 || { log "process: grok CLI missing; skipping"; continue; }
          log "processing new captures with grok ${MODEL:-default}"
          if grok -p "$PROCESS_PROMPT" ${MODEL:+--model "$MODEL"} \
            >> "$LOG_DIR/ingest-grok.log" 2>&1; then
            PROCESS_OK=1; log "process: filed by grok ${MODEL:-default}"; break
          fi
          log "WARN: grok ${MODEL:-default} failed; sliding to next model"
          ;;
        *)
          log "WARN: unknown runner '$RUNNER' in models.process; skipping"
          ;;
      esac
    done < <(brain_py "$ROOT/scripts/config.py" --process-chain)
    [[ "$PROCESS_OK" == "1" ]] || log "WARN: processing failed on every configured model; captures are still archived"
  fi

  git add -A Sources Topics Library People Projects Profile Meetings
  git commit -m "Daily ingest $(date +%Y-%m-%d)" --quiet || log "nothing to commit"

  log "digest: writing Digests/$(date +%Y-%m-%d).md"
  brain_py "$ROOT/scripts/digest.py" || log "WARN: digest failed"
  if [[ -n "$(git status --porcelain Digests/)" ]]; then
    git add Digests && git commit -m "Digest $(date +%Y-%m-%d)" --quiet || true
  fi
fi

if [[ "${BRAIN_X_DELETE:-1}" == "1" && "$PROCESS_OK" == "1" ]] && brain_source_enabled x_bookmarks; then
  log "cleanup: removing archived+processed bookmarks from X"
  brain_py "$ROOT/scripts/x_bookmarks_cleanup.py" \
    || log "WARN: X bookmark cleanup failed; will retry next run"
else
  log "cleanup skipped (processing incomplete, source off, or BRAIN_X_DELETE=0)"
fi

log "git push origin $BRANCH"
brain_git_push || log "WARN: push failed; commits remain local"

# New podcast episodes: only look back a couple weeks so old episodes trip the
# stale-stop quickly. backfill.sh dedupes and self-commits/pushes.
if brain_source_enabled podcasts && [[ "${BRAIN_PODCASTS:-1}" == "1" ]]; then
  # Interest-depth shows (YouTube + Claude synth). Skip world-context keys —
  # those use monthly digests, not per-episode notes.
  if command -v claude >/dev/null 2>&1; then
    log "podcasts: pulling new episodes (depth shows)"
    DEPTH_SHOWS="$("$ROOT/.venv/bin/python3" -c "
import json
from pathlib import Path
s=json.loads(Path('$ROOT/scripts/podcasts/shows.json').read_text())
print(' '.join(k for k,v in s.items() if v.get('role')!='world-context'))
")"
    CUTOFF="$(date -v-14d +%Y%m%d 2>/dev/null || date -d '14 days ago' +%Y%m%d)" \
      STALE_STOP=3 "$ROOT/scripts/podcasts/backfill.sh" $DEPTH_SHOWS \
      >> "$LOG_DIR/podcasts.log" 2>&1 \
      || log "WARN: podcast pull failed; will retry next run"
  else
    log "podcasts depth-synth skipped (no claude)"
  fi
  # World-context: refresh monthly digests only (lean, no per-episode notes)
  log "podcasts: consolidating world-context digests"
  "$ROOT/.venv/bin/python3" -c "
import json, subprocess, sys
from pathlib import Path
root = Path('$ROOT')
s = json.loads((root/'scripts/podcasts/shows.json').read_text())
for k,v in s.items():
    if v.get('role')=='world-context':
        r = subprocess.run([sys.executable, str(root/'scripts/podcasts/consolidate_world_context.py'), k], cwd=root)
        if r.returncode != 0:
            sys.exit(r.returncode)
" >> "$LOG_DIR/podcasts.log" 2>&1 || log "WARN: world-context consolidate failed"
  # commit month digests if dirty
  if [[ -n "$(git -C "$ROOT" status --porcelain Library/podcasts)" ]]; then
    git -C "$ROOT" add Library/podcasts
    git -C "$ROOT" commit -m "World-context digests $(date +%Y-%m-%d)" --quiet || true
    brain_git_push >/dev/null 2>&1 || true
  fi
else
  log "podcasts skipped (config or BRAIN_PODCASTS=0)"
fi

# New long-form YouTube likes (live LL pull; only unprocessed >=20min are judged).
if brain_source_enabled youtube_likes && [[ "${BRAIN_LIKES:-1}" == "1" ]] && command -v claude >/dev/null 2>&1; then
  log "youtube-likes: pulling new likes"
  JOBS=2 "$ROOT/scripts/youtube_likes/run.sh" 1200 \
    >> "$LOG_DIR/youtube-likes.log" 2>&1 \
    || log "WARN: youtube-likes pull failed; will retry next run"
else
  log "youtube-likes skipped (config or BRAIN_LIKES=0 or no claude)"
fi

log "done"
