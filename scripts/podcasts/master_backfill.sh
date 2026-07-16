#!/usr/bin/env bash
# One strict-sequential driver for a large first backfill, paced to survive
# YouTube's per-hour rate-limit. Reads YOUR shows from scripts/podcasts/shows.json:
#   1. wait for any current caption rate-limit ban to clear (poll)
#   2. every depth show, one at a time: grind until a full pass adds no new notes
#   3. long-form YouTube likes (paced)
# Everything self-commits/pushes. Restartable: just re-run this script.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
LOG="$ROOT/.status/master-backfill.log"
log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$LOG"; }

wait_for_youtube() {
  # Caption downloads are rate-limited more strictly than metadata, and synthesis
  # needs captions, so probe an actual transcript fetch on a known-captioned video.
  log "waiting for YouTube caption rate-limit to clear"
  local probe="/tmp/yt-probe.$$.txt"
  for i in $(seq 1 48); do
    rm -f "$probe"
    "$ROOT/.venv/bin/python3" "$ROOT/scripts/podcasts/fetch_transcript.py" \
      "pv1TUJSEM2k" "$probe" >/dev/null 2>&1
    if [[ -s "$probe" ]]; then
      rm -f "$probe"; log "captions available again (after ~$(( (i-1)*5 )) min)"; return 0
    fi
    sleep 300
  done
  log "still caption-limited after ~4h; proceeding anyway"
}

DEPTH_SHOWS="$("$ROOT/.venv/bin/python3" -c "
import json
from pathlib import Path
s = json.loads(Path('$ROOT/scripts/podcasts/shows.json').read_text())
print(' '.join(k for k, v in s.items() if v.get('role') != 'world-context'))
")"
[[ -n "$DEPTH_SHOWS" ]] || { log "no depth shows in scripts/podcasts/shows.json; fill it first (schema: shows.example.json)"; exit 1; }

wait_for_youtube
rm -rf "$ROOT/.status/podcasts.lock.d" 2>/dev/null

for SHOW in $DEPTH_SHOWS; do
  log "step: $SHOW grind (until a full pass adds nothing)"
  stagnant=0
  for pass in $(seq 1 300); do
    before=$(ls "$ROOT/Library/podcasts/$SHOW" 2>/dev/null | wc -l | tr -d ' ')
    rm -rf "$ROOT/.status/podcasts.lock.d" 2>/dev/null
    JOBS=2 SLEEP_BETWEEN=5 COOLDOWN=2700 \
      /bin/bash "$ROOT/scripts/podcasts/backfill.sh" "$SHOW" \
      >> "$ROOT/.status/backfill-$SHOW.log" 2>&1 || true
    after=$(ls "$ROOT/Library/podcasts/$SHOW" 2>/dev/null | wc -l | tr -d ' ')
    log "$SHOW pass $pass: $before -> $after notes"
    if (( after > before )); then
      stagnant=0
    elif tail -n 40 "$ROOT/.status/podcasts.log" 2>/dev/null | grep -q "RATE_LIMITED"; then
      log "$SHOW: no progress but rate-limited; cooling down 60m"; sleep 3600
    else
      stagnant=$((stagnant+1))
      (( stagnant >= 2 )) && { log "$SHOW complete ($after notes)"; break; }
    fi
  done
done

log "step: long-form YouTube likes (paced)"
JOBS=2 /bin/bash "$ROOT/scripts/youtube_likes/run.sh" 1200 \
  >> "$ROOT/.status/youtube-likes.log" 2>&1 || log "WARN: likes phase errored"

log "master: all done"
