#!/usr/bin/env bash
# Synthesize the substantive long-form YouTube likes. Parallel workers, each
# judging + writing its own note; music/gameplay/etc. are skipped. Shares the
# YouTube-access lock with the podcast backfill so the two never hammer YouTube
# at once (throttle safety). Restartable, self-commits/pushes.
#
#   run.sh [min_seconds]     (default 1200 = 20 min)
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HERE="$ROOT/scripts/youtube_likes"
mkdir -p "$ROOT/.status"
LOCK="$ROOT/.status/podcasts.lock.d"   # shared YouTube-access lock
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "YouTube-access lock held (podcast backfill or another likes run); exiting"; exit 0
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT INT TERM

MINSEC="${1:-1200}"
JOBS="${JOBS:-3}"
export BRAIN_LIKE_MODEL="${BRAIN_LIKE_MODEL:-claude-sonnet-5}"
LOG_DIR="$ROOT/.status"
log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }

commit_push() {
  cd "$ROOT"
  [[ -z "$(git status --porcelain Library People Topics)" ]] && return 0
  git add -A Library People Topics
  git commit -m "YouTube likes synthesis $(date +%Y-%m-%dT%H:%M)" --quiet || return 0
  git pull --rebase --autostash origin main >/dev/null 2>&1 || git rebase --abort 2>/dev/null
  git push origin main >/dev/null 2>&1 || log "WARN: push failed; commits local"
}

MANIFEST="$(mktemp -t yt-likes.XXXX)"
trap 'rm -f "$MANIFEST"; rmdir "$LOCK" 2>/dev/null' EXIT INT TERM
"$ROOT/.venv/bin/python3" "$HERE/select_candidates.py" "$MINSEC" > "$MANIFEST" 2>>"$LOG_DIR/youtube-likes.log"
TOTAL=$(wc -l < "$MANIFEST" | tr -d ' ')
log "likes: $TOTAL long-form candidates (>= ${MINSEC}s), $JOBS parallel"

running=0; done=0
while IFS=$'\t' read -r vid dur channel title; do
  [[ -z "$vid" ]] && continue
  "$HERE/synth_like.sh" "$vid" "$dur" "$channel" "$title" >> "$LOG_DIR/youtube-likes.log" 2>&1 &
  running=$((running+1))
  if (( running >= JOBS )); then
    wait; running=0; done=$((done+JOBS))
    log "likes: ~$done/$TOTAL judged"
    commit_push
  fi
done < "$MANIFEST"
wait
commit_push

log "likes: building link graph"
"$ROOT/.venv/bin/python3" "$ROOT/scripts/podcasts/build_links.py" >> "$LOG_DIR/youtube-likes.log" 2>&1 || log "WARN: build_links failed"
commit_push
log "likes: done"
