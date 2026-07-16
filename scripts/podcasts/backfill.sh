#!/usr/bin/env bash
# Two-phase podcast backfill.
#   Phase 1 (parallel): synth_episode.sh writes each episode's own note, JOBS at
#     a time. Workers never touch shared files, so parallelism is race-free.
#   Phase 2 (sequential): build_links.py materializes the People/Topics graph.
# Restartable (already-done episodes are skipped), self-commits/pushes.
#
#   backfill.sh [show_key ...]      (default: all shows in shows.json)
#
# Env: CUTOFF=YYYYMMDD (default: config podcasts.cutoff, else ChatGPT week),
#      JOBS=N parallel workers (default 2), BRAIN_POD_MODEL (default claude-sonnet-5),
#      COMMIT_EVERY=N batches (default 1).
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=../lib.sh
source "$ROOT/scripts/lib.sh"
HERE="$ROOT/scripts/podcasts"
mkdir -p "$ROOT/.status"
LOCK="$ROOT/.status/podcasts.lock.d"
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "another podcast backfill holds the lock; exiting"; exit 0
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT INT TERM

# Default cutoff: config.json podcasts.cutoff, else the week ChatGPT launched.
_CFG_CUTOFF="$("$ROOT/.venv/bin/python3" -c "import sys; sys.path.insert(0,'$ROOT/scripts'); from config import get; print(get('podcasts.cutoff') or '')" 2>/dev/null || true)"
export CUTOFF="${CUTOFF:-${_CFG_CUTOFF:-20221128}}"
export BRAIN_POD_MODEL="${BRAIN_POD_MODEL:-claude-sonnet-5}"
# YouTube rate-limits by account, so throughput is requests/hour, not
# concurrency. Keep parallelism low and pace batches to stay under the limit.
JOBS="${JOBS:-2}"
SLEEP_BETWEEN="${SLEEP_BETWEEN:-4}"
COOLDOWN="${COOLDOWN:-2700}"   # 45 min pause when YouTube rate-limits us
LOG_DIR="$ROOT/.status"
log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }

SHOWS=()
if [[ $# -gt 0 ]]; then for s in "$@"; do SHOWS+=("$s"); done
else while IFS= read -r s; do [[ -n "$s" ]] && SHOWS+=("$s"); done < <(
  "$ROOT/.venv/bin/python3" -c "import json;print('\n'.join(json.load(open('$HERE/shows.json'))))"); fi

commit_push() {
  cd "$ROOT"
  [[ -z "$(git status --porcelain Library People Topics)" ]] && return 0
  git add -A Library People Topics
  git commit -m "Podcast backfill $(date +%Y-%m-%dT%H:%M)" --quiet || return 0
  brain_git_pull >/dev/null 2>&1 || git -C "$ROOT" rebase --abort 2>/dev/null
  brain_git_push >/dev/null 2>&1 || log "WARN: push failed; commits local"
}

# Phase 1: enumerate + parallel synthesis, JOBS at a time, commit after each batch.
MANIFEST="$(mktemp -t pod-manifest.XXXX)"
trap 'rm -f "$MANIFEST"; rmdir "$LOCK" 2>/dev/null' EXIT INT TERM
for show in "${SHOWS[@]}"; do
  log "enumerating $show (cutoff $CUTOFF)"
  while IFS= read -r line; do
    [[ -n "$line" ]] && printf '%s\t%s\n' "$show" "$line" >> "$MANIFEST"
  done < <("$ROOT/.venv/bin/python3" "$HERE/enumerate_inrange.py" "$show" "$CUTOFF" 2>>"$LOG_DIR/podcasts.log")
done
TOTAL=$(wc -l < "$MANIFEST" | tr -d ' ')
log "phase 1: $TOTAL in-range episodes across ${#SHOWS[@]} show(s), $JOBS parallel"

running=0; done=0
while IFS=$'\t' read -r show vid date title; do
  [[ -z "$vid" ]] && continue
  "$HERE/synth_episode.sh" "$show" "$vid" "$date" "$title" >> "$LOG_DIR/podcasts.log" 2>&1 &
  running=$((running+1))
  if (( running >= JOBS )); then
    wait; running=0; done=$((done+JOBS))
    log "phase 1: ~$done/$TOTAL processed"
    commit_push
    # If this batch got rate-limited, back off hard before continuing.
    if tail -n "$JOBS" "$LOG_DIR/podcasts.log" 2>/dev/null | grep -q "RATE_LIMITED"; then
      log "phase 1: YouTube rate-limited; cooling down ${COOLDOWN}s"
      sleep "$COOLDOWN"
    else
      sleep "$SLEEP_BETWEEN"
    fi
  fi
done < "$MANIFEST"
wait
commit_push

# Phase 2: build the link graph (single writer), then commit.
log "phase 2: building People/Topics link graph"
"$ROOT/.venv/bin/python3" "$HERE/build_links.py" >> "$LOG_DIR/podcasts.log" 2>&1 || log "WARN: build_links failed"
commit_push
log "backfill done"
